"""Preflight check: everything that has to be true before a real run.

    uv run python -m rfactory.doctor

Each line is pass/fail with the fix attached, so a first run fails in the terminal
with an explanation rather than halfway through a graph with a stack trace.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from rfactory.config import settings

OK, WARN, FAIL = "  ok  ", " warn ", " FAIL "
_results: list[bool] = []


def report(status: str, label: str, detail: str = "") -> None:
    print(f"[{status}] {label}" + (f"\n         {detail}" if detail else ""))
    _results.append(status != FAIL)


def check_master() -> None:
    from rfactory.models.master import MasterResume

    try:
        master = MasterResume.load(settings.master_resume)
    except Exception as exc:
        report(FAIL, "master resume", f"{settings.master_resume}: {exc}")
        return
    counts = ", ".join(
        f"{t}: {len(master.experience_for(t))}r/{len(master.projects_for(t))}p"
        for t in master.tracks
    )
    report(OK, f"master resume (schema {master.schema_version})", counts)


def check_latex() -> None:
    engine = shutil.which(settings.latex_engine)
    if engine is None:
        report(FAIL, f"{settings.latex_engine}", "install MacTeX, or set RF_LATEX_ENGINE")
        return
    report(OK, f"{settings.latex_engine}", engine)

    kpsewhich = shutil.which("kpsewhich")
    if kpsewhich is None:
        report(WARN, "kpsewhich", "cannot verify LaTeX packages without it")
        return
    for package, needed_by in (
        ("sourcesanspro", "resume"),
        ("fontawesome5", "cover letter"),
        ("charter", "cover letter"),
    ):
        found = subprocess.run(
            [kpsewhich, f"{package}.sty"], capture_output=True, text=True
        ).stdout.strip()
        if found:
            report(OK, f"latex package {package}")
        else:
            report(FAIL, f"latex package {package}", f"needed by the {needed_by}; tlmgr install {package}")


def check_pdftotext() -> None:
    binary = shutil.which("pdftotext")
    if binary:
        report(OK, "pdftotext", binary)
    else:
        report(WARN, "pdftotext", "optional; without it the parse-back check uses one extractor")


def check_llm() -> None:
    import httpx

    from rfactory.llm.provider import active_endpoint

    endpoint = active_endpoint()
    if not endpoint.base_url:
        report(FAIL, f"{endpoint.name} endpoint", "not configured in .env")
        return

    headers = {"Authorization": f"Bearer {endpoint.api_key}"} if endpoint.api_key else {}
    try:
        response = httpx.get(f"{endpoint.base_url.rstrip('/')}/models", headers=headers, timeout=10.0)
        response.raise_for_status()
        ids = [m["id"] for m in response.json().get("data", [])]
    except Exception as exc:
        report(FAIL, f"{endpoint.name} at {endpoint.base_url}", f"{type(exc).__name__}: {exc}")
        return

    report(OK, f"{endpoint.name} reachable at {endpoint.base_url}", f"{len(ids)} model(s) available")
    if not endpoint.model:
        listing = "\n         ".join(ids[:15]) or "(none)"
        report(FAIL, "no model configured", f"set RF_{endpoint.name.upper()}_MODEL to one of:\n         {listing}")
    elif endpoint.model in ids:
        report(OK, f"model {endpoint.model!r} is available")
    else:
        listing = "\n         ".join(ids[:15]) or "(none available)"
        report(
            FAIL,
            f"model {endpoint.model!r} not found",
            f"set RF_{endpoint.name.upper()}_MODEL to one of:\n         {listing}",
        )


def check_roundtrip() -> None:
    """The check that actually matters: can this model return usable JSON, and is the
    server constraining it to a grammar or just being asked nicely?"""
    from rfactory.llm.prompts import INGEST_SYSTEM, INGEST_USER
    from rfactory.llm.provider import LLMError, complete_model, get_provider
    from rfactory.llm.schemas import JobPosting

    tiny = (
        "Senior AI Engineer. Python, RAG, prompt engineering, model evaluation, "
        "Kubernetes, Docker, Azure and AWS. Acme Corp, London."
    )
    try:
        provider = get_provider()
        result = complete_model(
            provider,
            INGEST_SYSTEM,
            INGEST_USER.format(jd_text=tiny),
            JobPosting,
            max_tokens=settings.max_tokens_ingest,
            retries=0,
        )
    except LLMError as exc:
        report(FAIL, "JSON round-trip", str(exc)[:400])
        return
    except Exception as exc:
        report(FAIL, "JSON round-trip", f"{type(exc).__name__}: {exc}")
        return

    stats = provider.last
    report(
        OK,
        "JSON round-trip",
        f"{stats}\n         parsed: company={result.company!r}, "
        f"{len(result.requirements)} requirement(s)",
    )
    if not stats.structured:
        report(
            WARN,
            "grammar-constrained output",
            "server rejected response_format, so reasoning is not suppressed by the "
            "grammar; expect slower calls and occasional empty responses",
        )


def check_render() -> None:
    from rfactory.models.master import MasterResume
    from rfactory.render.resume import baseline_draft, render_pdf

    try:
        master = MasterResume.load(settings.master_resume)
        track = master.tracks[0]
        result = render_pdf(baseline_draft(master, track, role="Preflight"))
    except Exception as exc:
        report(FAIL, "LaTeX render", f"{type(exc).__name__}: {exc}")
        return
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as handle:
        handle.write(result.pdf)
    report(OK, f"LaTeX render ({track})", f"{result.pages} page, {Path(handle.name)}")


def main() -> int:
    from rfactory.llm.provider import active_endpoint as _endpoint

    active = _endpoint()
    print(
        f"resume-factory preflight\n"
        f"repo:     {settings.master_resume.parent.parent}\n"
        f"provider: {active.name} -> {active.base_url or '(unset)'}\n"
    )
    for check in (check_master, check_latex, check_pdftotext, check_llm, check_roundtrip, check_render):
        check()
    failures = _results.count(False)
    print(f"\n{len(_results) - failures} passed, {failures} failed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
