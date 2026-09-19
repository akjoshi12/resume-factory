from __future__ import annotations

import httpx

from rfactory.config import settings
from rfactory.graph.state import GraphState
from rfactory.llm.prompts import INGEST_SYSTEM, INGEST_USER
from rfactory.llm.provider import complete_model, get_provider
from rfactory.llm.schemas import JobPosting

MAX_JD_CHARS = 12000


def fetch_jd(url: str, *, timeout: float = 8.0) -> str:
    """Best effort. LinkedIn, Indeed and most Workday-hosted postings sit behind a login
    wall or bot check, so failure is the expected path often enough that it must never
    block: the UI falls back to a pasted description."""
    try:
        import trafilatura

        headers = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"}
        with httpx.Client(follow_redirects=True, timeout=timeout, headers=headers) as client:
            response = client.get(url)
            response.raise_for_status()
        return trafilatura.extract(response.text) or ""
    except Exception:
        return ""


def ingest_jd(state: GraphState) -> dict:
    text = (state.get("jd_text") or "").strip()
    errors = list(state.get("errors") or [])

    if not text and (url := state.get("jd_url")):
        text = fetch_jd(url)
        if not text:
            errors.append(f"could not fetch {url}; paste the description instead")

    if not text:
        return {"errors": errors, "stage": "needs_jd"}

    posting = complete_model(
        get_provider(state.get("llm_provider"), state.get("llm_model")),
        INGEST_SYSTEM,
        INGEST_USER.format(jd_text=text[:MAX_JD_CHARS]),
        JobPosting,
        max_tokens=settings.max_tokens_ingest,
        acceptable=lambda posting: bool(posting.requirements),
    )
    return {
        "jd_text": text,
        "company": state.get("company") or posting.company,
        "role_title": state.get("role_title") or posting.role_title,
        "requirements": posting.requirements,
        "errors": errors,
        "stage": "tailoring",
    }
