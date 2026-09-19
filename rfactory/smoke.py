"""LLM-free end-to-end check: master resume -> LaTeX -> PDF -> parse back.

    uv run python -m rfactory.smoke [track]

Proves the mechanical path (template, escaping, compile, page fit, extractability)
before any model is allowed near the content.
"""

from __future__ import annotations

import sys

from rfactory.config import settings
from rfactory.models.master import MasterResume
from rfactory.render.resume import baseline_draft, render_pdf, render_tex
from rfactory.scoring import parseback


def main() -> int:
    track = sys.argv[1] if len(sys.argv) > 1 else "ai_eng"
    master = MasterResume.load(settings.master_resume)
    if track not in master.tracks:
        print(f"unknown track {track!r}; known: {', '.join(master.tracks)}")
        return 2

    draft = baseline_draft(master, track)
    tex = render_tex(draft)
    result = render_pdf(draft)

    settings.out_dir.mkdir(parents=True, exist_ok=True)
    (settings.out_dir / f"resume_{track}.tex").write_text(tex, encoding="utf-8")
    (settings.out_dir / f"resume_{track}.pdf").write_bytes(result.pdf)

    report = parseback.check(result.pdf, draft)
    roles = draft.bullet_count()

    print(f"track            {track}")
    print(f"roles            {len(draft.professional)} + {len(draft.additional)} additional")
    print(f"bullets          {roles}")
    print(f"projects         {len(draft.projects)}")
    print(f"skill groups     {len(draft.skills)}")
    print(f"activities       {len(draft.activities)}")
    print(f"certifications   {len(draft.certifications)}")
    print(f"pages            {result.pages}")
    print(f"parse-back       {'ok' if report.ok else 'MISSING ' + ', '.join(report.missing)}")
    for name, misses in report.by_extractor.items():
        print(f"  via {name:<12} {'ok' if not misses else str(len(misses)) + ' missed'}")
    print(f"spacing risk     {'YES - words merge under a lenient parser' if report.spacing_risk else 'no'}")
    print(f"output           {settings.out_dir / f'resume_{track}.pdf'}")

    over = result.pages > settings.max_pages
    if over:
        print(f"\nFAIL: {result.pages} pages, limit is {settings.max_pages}")
    return 1 if (over or not report.ok) else 0


if __name__ == "__main__":
    raise SystemExit(main())
