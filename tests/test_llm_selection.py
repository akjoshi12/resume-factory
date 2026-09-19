"""Candidate selection and model override.

The bug these guard against: every schema gives its fields defaults, so `{}` validates.
Combined with picking the last JSON value out of a reasoning stream, a stray brace can
be accepted as the answer and surface much later as an empty cover letter.
"""

from __future__ import annotations

import json

import pytest

from rfactory.llm.provider import CallStats, LLMError, complete_model, get_provider, json_candidates
from rfactory.llm.schemas import CoverLetterBody


class Scripted:
    name = "scripted"

    def __init__(self, reply: str):
        self.reply = reply
        self.last = CallStats()
        self.calls = 0

    def complete(self, system, user, *, temperature=0.2, max_tokens=None, schema=None,
                 schema_name="response"):  # noqa: ANN001
        self.calls += 1
        return self.reply


REASONING_WITH_STRAY_BRACE = (
    "Let me plan the letter. Structure: an opening, two body paragraphs, a close.\n"
    '{"recipient": "Hiring Manager", "paragraphs": ["Opening paragraph here.", '
    '"Second paragraph with evidence.", "Closing."]}\n'
    "Wait, I should double-check the schema shape: {\"recipient\": \"\", \"paragraphs\": []}"
)


def test_a_valid_but_empty_candidate_is_rejected_in_favour_of_the_real_one():
    provider = Scripted(REASONING_WITH_STRAY_BRACE)
    assert len(json_candidates(REASONING_WITH_STRAY_BRACE)) == 2

    body = complete_model(
        provider, "sys", "user", CoverLetterBody, retries=0,
        acceptable=lambda b: len([p for p in b.paragraphs if p.strip()]) >= 2,
    )
    assert len(body.paragraphs) == 3
    assert body.paragraphs[0].startswith("Opening")


def test_without_the_predicate_the_empty_one_would_win():
    """Documents why the predicate exists rather than trusting last-wins alone."""
    provider = Scripted(REASONING_WITH_STRAY_BRACE)
    body = complete_model(provider, "sys", "user", CoverLetterBody, retries=0)
    assert body.paragraphs == [], "last-wins alone picks the trailing stray object"


def test_all_candidates_empty_fails_loudly_with_a_useful_message():
    provider = Scripted('thinking... {"paragraphs": []} and {"recipient": "x"}')
    with pytest.raises(LLMError) as caught:
        complete_model(
            provider, "sys", "user", CoverLetterBody, retries=0,
            acceptable=lambda b: len(b.paragraphs) >= 2,
        )
    assert "empty or incomplete" in str(caught.value)


def test_model_override_beats_the_configured_default(monkeypatch):
    from rfactory.config import settings

    monkeypatch.setattr(settings, "llm_provider", "lmstudio")
    monkeypatch.setattr(settings, "lmstudio_model", "configured-model")

    assert get_provider().model == "configured-model"
    assert get_provider(model="switched-model").model == "switched-model"


def test_unconfigured_provider_names_the_env_vars(monkeypatch):
    from rfactory.config import settings

    monkeypatch.setattr(settings, "llm_provider", "cloud")
    monkeypatch.setattr(settings, "cloud_base_url", "")
    with pytest.raises(LLMError) as caught:
        get_provider()
    assert "RF_CLOUD_BASE_URL" in str(caught.value)


def test_json_candidates_survives_a_stream_with_no_json():
    assert json_candidates("I am thinking about this and produced nothing.") == []
    _ = json.dumps  # keep the import meaningful
