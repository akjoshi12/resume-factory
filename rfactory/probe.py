"""Dump exactly what the local server returns, with nothing in between.

    uv run python -m rfactory.probe

Raw httpx, not the OpenAI SDK, so no client-side normalisation can hide a field. Runs
the same minimal request four ways -- plain, with thinking disabled, with a JSON
schema, and with both -- and prints finish_reason, every key present on the message,
and the repr of each candidate content field.

Use this when a call returns empty content. It answers the only question that matters:
did the server put the answer somewhere other than message.content, or did it truly
generate nothing?
"""

from __future__ import annotations

import json
from typing import Any

import httpx

from rfactory.config import settings
from rfactory.llm.provider import active_endpoint

SYSTEM = "You extract structured facts from job postings."
USER = (
    "Extract the company and role title from this posting:\n\n"
    "Senior AI Engineer at Acme Corp, London. Python, RAG, Kubernetes.\n\n"
    'Return ONLY JSON: {"company": "...", "role_title": "..."}'
)

SCHEMA = {
    "type": "object",
    "properties": {"company": {"type": "string"}, "role_title": {"type": "string"}},
    "required": ["company", "role_title"],
}

CONTENT_FIELDS = ("content", "reasoning_content", "reasoning", "thinking", "text")


def _post(label: str, body: dict[str, Any]) -> None:
    endpoint = active_endpoint()
    url = f"{endpoint.base_url.rstrip('/')}/chat/completions"
    print(f"\n{'=' * 70}\n{label}\n{'=' * 70}")
    print("request extras:", json.dumps({k: v for k, v in body.items() if k not in
                                         ("model", "messages", "temperature")}, default=str)[:300])
    headers = {"Authorization": f"Bearer {endpoint.api_key}"} if endpoint.api_key else {}
    try:
        response = httpx.post(url, json=body, headers=headers, timeout=settings.request_timeout)
    except Exception as exc:
        print(f"  TRANSPORT ERROR {type(exc).__name__}: {exc}")
        return

    print(f"  HTTP {response.status_code}")
    if response.status_code != 200:
        print("  body:", response.text[:1200])
        return

    payload = response.json()
    choice = (payload.get("choices") or [{}])[0]
    message = choice.get("message") or {}
    print(f"  finish_reason: {choice.get('finish_reason')!r}")
    print(f"  usage:         {payload.get('usage')}")
    print(f"  message keys:  {sorted(message.keys())}")
    for field in CONTENT_FIELDS:
        if field in message:
            value = message[field]
            shown = value if isinstance(value, str) else json.dumps(value)
            print(f"  {field:18} len={len(shown or '')!s:<6} {(shown or '')[:220]!r}")
    extras = set(message) - set(CONTENT_FIELDS) - {"role", "tool_calls", "function_call"}
    for field in sorted(extras):
        print(f"  {field:18} {str(message[field])[:200]!r}")


def main() -> int:
    endpoint = active_endpoint()
    base = endpoint.base_url.rstrip("/")
    auth = {"Authorization": f"Bearer {endpoint.api_key}"} if endpoint.api_key else {}
    print(f"provider: {endpoint.name}\nendpoint: {base}\nconfigured model: {endpoint.model!r}")
    try:
        models = httpx.get(f"{base}/models", headers=auth, timeout=15.0).json()
        ids = [m["id"] for m in models.get("data", [])]
        print(f"loaded models: {ids}")
        if endpoint.model not in ids:
            print(f"  !! configured model is NOT in that list -- set RF_{endpoint.name.upper()}_MODEL")
    except Exception as exc:
        print(f"  cannot list models: {type(exc).__name__}: {exc}")
        return 1

    base_body: dict[str, Any] = {
        "model": endpoint.model,
        "temperature": 0.2,
        "max_tokens": 400,
        "messages": [{"role": "system", "content": SYSTEM}, {"role": "user", "content": USER}],
    }
    schema_body = {
        "type": "json_schema",
        "json_schema": {"name": "JobPosting", "schema": SCHEMA, "strict": False},
    }

    _post("1. plain (no extras)", dict(base_body))
    _post("2. chat_template_kwargs enable_thinking=false",
          {**base_body, "chat_template_kwargs": {"enable_thinking": False}})
    _post("3. response_format json_schema", {**base_body, "response_format": schema_body})
    _post("4. both",
          {**base_body, "response_format": schema_body,
           "chat_template_kwargs": {"enable_thinking": False}})

    print(
        "\nWhat to look for:\n"
        "  - content empty but reasoning_content full -> the server split the answer out;\n"
        "    the fix is to read that field.\n"
        "  - content empty everywhere with finish_reason 'stop' and completion_tokens > 0\n"
        "    -> tokens were generated and discarded, usually a chat-template mismatch.\n"
        "  - case 3 or 4 returning HTTP 400 -> no grammar support; set\n"
        "    RF_STRUCTURED_OUTPUT=false and rely on the prompt path.\n"
        "  - one case succeeding where others do not tells us exactly what to send."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
