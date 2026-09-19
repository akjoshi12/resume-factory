"""Pluggable LLM access. One OpenAI-compatible client serves both LM Studio locally
and any hosted endpoint, so switching is a config change rather than a code path.

Three things matter for local models and are handled here rather than hoped for.

Structured output. The schema is handed to the server via `response_format`, which
constrains generation to a grammar. The model cannot emit a reasoning block, prose or
a code fence, because the first token has to be `{`. This is the reliable fix; asking
for JSON in the prompt is not. Servers that reject `response_format` fall back to
prompting, and the fallback is recorded rather than hidden.

Reasoning. On the fallback path Qwen3-class models still emit a <think> phase. It is
uncapped, absent from the completion count, and will happily consume an entire
max_tokens budget before writing any answer -- which surfaces as an empty response
with finish_reason "length". That case gets its own diagnosis.

Budget. Every call is capped and timed, and SDK-level retries are off: on a local
model they turn a stall into a silent multi-minute wait.
"""

from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import dataclass, replace
from collections.abc import Callable
from typing import Any, Protocol, TypeVar

from pydantic import BaseModel, ValidationError

from rfactory.config import settings

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)

_THINK = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)
_OPEN_THINK = re.compile(r"^.*?</think>", re.DOTALL | re.IGNORECASE)
_FENCE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL)

# Fields servers use when they split reasoning out of the main content.
ALT_CONTENT_FIELDS = ("reasoning_content", "reasoning", "thinking")

EMPTY_AND_TRUNCATED = (
    "the model returned no content and hit the {cap}-token cap, meaning it spent the "
    "whole budget on its reasoning phase before writing any answer. Fixes, in order: "
    "leave RF_STRUCTURED_OUTPUT=true so the server constrains output to JSON; turn "
    "reasoning off for the model in LM Studio; or raise RF_MAX_TOKENS_*."
)

EMPTY_AND_STOPPED = (
    "the model returned empty content and stopped of its own accord "
    "(finish_reason={reason!r}, {completion} completion tokens, schema={structured}). "
    "Fields present on the message: {keys}. Nothing was truncated, so this is not a "
    "token budget problem -- the server either discarded the output or put it "
    "somewhere this client does not read. Run `python -m rfactory.probe` to see the "
    "raw response; it distinguishes those two cases."
)


class LLMError(RuntimeError):
    pass


@dataclass(slots=True)
class CallStats:
    elapsed: float = 0.0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    truncated: bool = False
    structured: bool = False

    @property
    def tokens_per_second(self) -> float:
        return self.completion_tokens / self.elapsed if self.elapsed else 0.0

    def __str__(self) -> str:
        return (
            f"{self.elapsed:.1f}s, {self.prompt_tokens} in / {self.completion_tokens} out"
            f" ({self.tokens_per_second:.1f} tok/s)"
            f"{' schema' if self.structured else ' prompt-only'}"
            f"{' TRUNCATED' if self.truncated else ''}"
        )


def inline_refs(schema: dict[str, Any]) -> dict[str, Any]:
    """Resolve $ref/$defs into a single self-contained schema.

    Pydantic emits nested models as $refs. Server-side grammar compilers vary in how
    well they follow them, and a schema that fails to compile usually degrades to
    unconstrained generation rather than a clear error, so it is safer to send a flat
    one. Recursive models would not terminate here, and this app has none.
    """
    defs = schema.get("$defs", {})

    def resolve(node: Any) -> Any:
        if isinstance(node, dict):
            if "$ref" in node:
                name = node["$ref"].rsplit("/", 1)[-1]
                merged = {k: v for k, v in node.items() if k != "$ref"}
                return {**resolve(defs.get(name, {})), **merged}
            return {k: resolve(v) for k, v in node.items() if k != "$defs"}
        if isinstance(node, list):
            return [resolve(item) for item in node]
        return node

    return resolve({k: v for k, v in schema.items() if k != "$defs"})


def _strip_reasoning(raw: str) -> str:
    """Remove think blocks, but never return empty: when the whole reply came from a
    reasoning field there are no tags to strip and the text itself is all we have."""
    text = _THINK.sub("", raw)
    if "</think>" in text:  # a block whose opening tag was never emitted
        text = _OPEN_THINK.sub("", text)
    return text.strip() or raw.strip()


def _scan(text: str) -> list[str]:
    """Every balanced top-level JSON object or array in the text, in order."""
    found: list[str] = []
    index = 0
    while index < len(text):
        start = min((i for i in (text.find("{", index), text.find("[", index)) if i != -1),
                    default=-1)
        if start == -1:
            break
        opening = text[start]
        closing = "}" if opening == "{" else "]"
        depth, in_string, escaped = 0, False, False
        end = -1
        for i, ch in enumerate(text[start:], start):
            if in_string:
                if escaped:
                    escaped = False
                elif ch == "\\":
                    escaped = True
                elif ch == '"':
                    in_string = False
                continue
            if ch == '"':
                in_string = True
            elif ch == opening:
                depth += 1
            elif ch == closing:
                depth -= 1
                if depth == 0:
                    end = i
                    break
        if end == -1:
            break
        found.append(text[start : end + 1])
        index = end + 1
    return found


def json_candidates(raw: str) -> list[str]:
    """Candidate JSON values, best last.

    A reasoning stream routinely contains a sketch of the answer before the answer
    itself, so the final complete value is the one to trust. Fenced blocks are scanned
    first because a model that bothered to fence something meant that to be the output.
    """
    text = _strip_reasoning(raw)
    candidates: list[str] = []
    for block in _FENCE.findall(text):
        candidates.extend(_scan(block))
    candidates.extend(c for c in _scan(text) if c not in candidates)
    return candidates


def extract_json(raw: str) -> str:
    candidates = json_candidates(raw)
    if not candidates:
        raise LLMError(f"no JSON found in response: {raw[:300]!r}")
    return candidates[-1]


class LLMProvider(Protocol):
    name: str
    last: CallStats

    def complete(
        self,
        system: str,
        user: str,
        *,
        temperature: float = 0.2,
        max_tokens: int | None = None,
        schema: dict[str, Any] | None = None,
        schema_name: str = "response",
    ) -> str: ...


class OpenAICompatProvider:
    def __init__(self, base_url: str, model: str, api_key: str = "not-needed", name: str = "llm"):
        from openai import OpenAI

        self.name = name
        self.model = model
        self.last = CallStats()
        self.supports_schema = settings.structured_output
        self._client = OpenAI(
            base_url=base_url,
            api_key=api_key or "not-needed",
            timeout=settings.request_timeout,
            # The SDK retries timeouts twice by default. On a local model where one
            # call is already a minute or two, that turns a stall into a silent
            # multi-minute wait. complete_model retries bad JSON, which is the
            # failure actually worth retrying.
            max_retries=0,
        )

    def complete(
        self,
        system: str,
        user: str,
        *,
        temperature: float = 0.2,
        max_tokens: int | None = None,
        schema: dict[str, Any] | None = None,
        schema_name: str = "response",
    ) -> str:
        from openai import APIStatusError

        messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
        extra: dict[str, Any] = {}
        if settings.disable_thinking:
            # Recognised by LM Studio, vLLM and Ollama for Qwen3-style templates;
            # servers that do not know it ignore it. Belt to the schema's braces.
            extra["chat_template_kwargs"] = {"enable_thinking": False}

        use_schema = bool(schema) and self.supports_schema
        started = time.monotonic()
        try:
            response = self._call(messages, temperature, max_tokens, extra,
                                  schema if use_schema else None, schema_name)
        except APIStatusError as exc:
            if not use_schema or exc.status_code not in (400, 404, 422, 501):
                raise
            logger.warning(
                "%s rejected response_format (%s); falling back to prompt-only JSON. "
                "Reasoning is no longer suppressed by the grammar.",
                self.name,
                exc.status_code,
            )
            self.supports_schema = False
            use_schema = False
            response = self._call(messages, temperature, max_tokens, extra, None, schema_name)

        choice = response.choices[0]
        usage = response.usage
        self.last = CallStats(
            elapsed=time.monotonic() - started,
            prompt_tokens=getattr(usage, "prompt_tokens", 0) or 0,
            completion_tokens=getattr(usage, "completion_tokens", 0) or 0,
            truncated=choice.finish_reason == "length",
            structured=use_schema,
        )
        logger.info("%s call: %s", self.name, self.last)

        message = choice.message
        content = (message.content or "").strip()

        if not content:
            # Some servers return the answer in a reasoning field and leave content
            # empty. Prefer a real answer over a clean abstraction.
            extra = getattr(message, "model_extra", None) or {}
            for field in ALT_CONTENT_FIELDS:
                candidate = getattr(message, field, None) or extra.get(field)
                if isinstance(candidate, str) and candidate.strip():
                    logger.warning(
                        "%s returned empty content; reading message.%s instead",
                        self.name,
                        field,
                    )
                    content = candidate.strip()
                    break

        if not content:
            if self.last.truncated:
                raise LLMError(EMPTY_AND_TRUNCATED.format(cap=max_tokens))
            keys = sorted(set(message.model_dump(exclude_none=True))) if hasattr(
                message, "model_dump"
            ) else []
            raise LLMError(
                EMPTY_AND_STOPPED.format(
                    reason=choice.finish_reason,
                    completion=self.last.completion_tokens,
                    structured=use_schema,
                    keys=keys or "unknown",
                )
            )

        if self.last.truncated:
            logger.warning("%s hit the %s-token cap; output was cut mid-answer", self.name, max_tokens)
        return content

    def _call(self, messages, temperature, max_tokens, extra, schema, schema_name):  # type: ignore[no-untyped-def]
        kwargs: dict[str, Any] = {
            "model": self.model,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "messages": messages,
        }
        if schema:
            kwargs["response_format"] = {
                "type": "json_schema",
                "json_schema": {"name": schema_name, "schema": schema, "strict": False},
            }
        return self._client.chat.completions.create(**kwargs, extra_body=extra or None)


@dataclass(slots=True)
class Endpoint:
    name: str
    base_url: str
    model: str
    api_key: str = ""


def active_endpoint(override: str | None = None) -> Endpoint:
    """Resolve which endpoint is in play. One place, so doctor, probe, bench and the
    graph never disagree about what is being talked to."""
    choice = (override or settings.llm_provider).lower()
    if choice == "gateway":
        return Endpoint(
            "gateway", settings.gateway_base_url, settings.gateway_model, settings.gateway_api_key
        )
    if choice == "cloud":
        return Endpoint("cloud", settings.cloud_base_url, settings.cloud_model, settings.cloud_api_key)
    return Endpoint("lmstudio", settings.lmstudio_base_url, settings.lmstudio_model)


def available_models(provider: str | None = None) -> list[str]:
    """Model ids the configured endpoint is serving, for the UI's picker. Returns []
    rather than raising: a dropdown that cannot be filled is not a fatal condition."""
    import httpx

    endpoint = active_endpoint(provider)
    if not endpoint.base_url:
        return []
    headers = {"Authorization": f"Bearer {endpoint.api_key}"} if endpoint.api_key else {}
    try:
        response = httpx.get(
            f"{endpoint.base_url.rstrip('/')}/models", headers=headers, timeout=10.0
        )
        response.raise_for_status()
        return sorted(m["id"] for m in response.json().get("data", []))
    except Exception:
        logger.warning("could not list models for %s at %s", endpoint.name, endpoint.base_url)
        return []


def get_provider(provider: str | None = None, model: str | None = None) -> LLMProvider:
    """model overrides the configured default for this call only, so the UI can switch
    models between the resume and the cover letter without touching .env."""
    endpoint = active_endpoint(provider)
    if model:
        endpoint = replace(endpoint, model=model)
    if not endpoint.base_url or not endpoint.model:
        prefix = f"RF_{endpoint.name.upper()}"
        raise LLMError(
            f"{prefix}_BASE_URL and {prefix}_MODEL must both be set for the "
            f"{endpoint.name!r} provider (RF_LLM_PROVIDER={settings.llm_provider!r})"
        )
    return OpenAICompatProvider(
        endpoint.base_url, endpoint.model, endpoint.api_key, name=endpoint.name
    )


def complete_model(
    provider: LLMProvider,
    system: str,
    user: str,
    model_cls: type[T],
    *,
    temperature: float = 0.2,
    retries: int = 1,
    max_tokens: int | None = None,
    acceptable: Callable[[T], bool] | None = None,
) -> T:
    """Ask for JSON matching model_cls, constrained by the schema where the server
    supports it. On a parse or validation failure, retry once with the error handed
    back, then give up loudly rather than returning junk.

    `acceptable` exists because validating is not the same as being the answer. Every
    schema here gives its fields defaults, so an empty object validates perfectly --
    and a reasoning stream is full of stray braces. Without a usefulness test the
    picker can return a structurally valid, semantically empty result, which surfaces
    much later as a cover letter with no paragraphs.
    """
    schema = inline_refs(model_cls.model_json_schema())
    prompt = (
        f"{user}\n\nReturn ONLY JSON matching this schema. No prose, no markdown, "
        f"no reasoning.\n{json.dumps(schema)}"
    )

    last_error = ""
    for attempt in range(retries + 1):
        payload = prompt if attempt == 0 else f"{prompt}\n\nYour last reply was invalid: {last_error}"
        raw = provider.complete(
            system,
            payload,
            temperature=temperature,
            max_tokens=max_tokens,
            schema=schema,
            schema_name=model_cls.__name__,
        )
        candidates = json_candidates(raw)
        if not candidates:
            last_error = f"no JSON found in response: {raw[:200]!r}"
        # Last first: in a reasoning stream the final complete value is the answer,
        # and anything earlier is usually the model sketching one.
        rejected_as_empty = 0
        for candidate in reversed(candidates):
            try:
                parsed = model_cls.model_validate_json(candidate)
            except (ValidationError, json.JSONDecodeError) as exc:
                last_error = str(exc)[:400]
                continue
            if acceptable is not None and not acceptable(parsed):
                rejected_as_empty += 1
                continue
            return parsed
        if rejected_as_empty:
            last_error = (
                f"{rejected_as_empty} of {len(candidates)} JSON value(s) parsed but were "
                f"empty or incomplete for {model_cls.__name__}. The model most likely "
                "emitted its answer inside a reasoning block that got truncated."
            )
        if getattr(provider, "last", None) and provider.last.truncated:
            last_error = f"response was cut off at the token limit. {last_error}"
    raise LLMError(f"{provider.name} failed to produce valid {model_cls.__name__}: {last_error}")
