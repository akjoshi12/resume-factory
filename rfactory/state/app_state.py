from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from typing import Any

import reflex as rx
from reflex.config import get_config

from rfactory import scan, service
from rfactory.config import settings
from rfactory.db.models import Outcome
from rfactory.llm.provider import available_models
from rfactory.models.master import MasterResume

# Fields AJ marked non-editable. They are rendered as read-only text, never as inputs,
# so the UI cannot be the route by which a title or a date changes.
LOCKED_NOTE = "Locked: name, links, role titles, dates, education"

# PDFs are served by the backend, which runs on a different port from the frontend.
# A relative /api/... URL resolves against the frontend origin and 404s.
API_BASE = get_config().api_url.rstrip("/")


@dataclass
class EditBullet:
    key: str = ""  # "<role_id>:<index>" -- the address an event handler edits by
    role_id: str = ""
    index: int = 0
    bullet_id: str = ""
    text: str = ""
    source: str = ""  # the approved master text, shown alongside for comparison


@dataclass
class EditRole:
    id: str = ""
    title: str = ""
    org: str = ""
    date_range: str = ""
    section: str = ""


@dataclass
class EditSkillGroup:
    key: str = ""
    label: str = ""
    # NOT 'entries': Reflex's ObjectVar has an .entries() method that shadows a
    # field of that name inside rx.foreach.
    joined: str = ""


@dataclass
class EditParagraph:
    index: int = 0
    text: str = ""


@dataclass
class AppRow:
    id: str = ""
    company: str = ""
    role_title: str = ""
    track: str = ""
    stage: str = ""
    outcome: str = ""
    coverage: str = ""
    ats: str = ""
    created: str = ""
    model: str = ""


class AppState(rx.State):
    # dashboard -------------------------------------------------------------
    applications: list[AppRow] = []
    outcomes: list[str] = [o.value for o in Outcome]
    # Tallied from each application's outcome, which you set per row once you hear back.
    stat_total: int = 0
    stat_waiting: int = 0
    stat_interviews: int = 0
    stat_rejected: int = 0

    # quick scan
    scanning: bool = False
    scan_done: bool = False
    scan_match: int = 0
    scan_verdict: str = ""
    scan_reason: str = ""
    scan_strengths: list[str] = []
    scan_gaps: list[str] = []
    scan_tools_have: list[str] = []
    scan_tools_missing: list[str] = []
    scan_ats_ceiling: int = 0

    # new application -------------------------------------------------------
    tracks: list[str] = []
    track: str = ""
    jd_url: str = ""
    jd_text: str = ""
    company: str = ""
    role_title: str = ""

    # model choice
    providers: list[str] = ["lmstudio", "gateway", "cloud"]
    provider: str = ""
    models: list[str] = []
    model: str = ""
    models_error: str = ""

    # delete confirmation
    pending_delete: str = ""

    # review ----------------------------------------------------------------
    current_id: str = ""
    # Bumped every time a gate re-fires. The PDF is rewritten to the same path, so
    # without a changing URL the browser keeps showing the copy it already cached
    # and an edit looks like it did nothing.
    preview_nonce: int = 0
    gate: str = ""  # "resume" | "cover" | "complete" | ""
    busy: bool = False
    status: str = ""
    error: str = ""

    objective: str = ""
    header_role: str = ""
    roles: list[EditRole] = []
    bullets: list[EditBullet] = []
    skill_groups: list[EditSkillGroup] = []
    certifications: list[str] = []

    pages: int = 0
    coverage_summary: str = ""
    coverage_missing: list[str] = []
    ats_score: int = -1
    ats_ceiling: int = -1
    ats_phrases_missing: list[str] = []
    ats_parts: str = ""
    ats_tools_missing: list[str] = []
    violations: list[str] = []
    notes: list[str] = []
    trim_log: list[str] = []
    parse_ok: bool = True
    spacing_risk: bool = False

    feedback: str = ""
    cover_paragraphs: list[EditParagraph] = []

    _draft: dict[str, Any] = {}
    _cover: dict[str, Any] = {}

    # -- form setters -------------------------------------------------------
    # Reflex 0.9 dropped auto-generated set_* handlers, so these are declared.

    @rx.event
    def set_track(self, value: str):
        self.track = value

    @rx.event
    def set_jd_url(self, value: str):
        self.jd_url = value

    @rx.event
    def set_jd_text(self, value: str):
        self.jd_text = value

    @rx.event
    def set_company(self, value: str):
        self.company = value

    @rx.event
    def set_role_title(self, value: str):
        self.role_title = value

    @rx.event
    def set_objective(self, value: str):
        self.objective = value

    @rx.event
    def set_header_role(self, value: str):
        self.header_role = value

    @rx.event
    def set_feedback(self, value: str):
        self.feedback = value

    # -- loading ------------------------------------------------------------

    @rx.var
    def has_violations(self) -> bool:
        return len(self.violations) > 0

    @rx.var
    def has_notes(self) -> bool:
        return len(self.notes) > 0

    @rx.var
    def over_length(self) -> bool:
        return self.pages > settings.max_pages

    @rx.var
    def resume_pdf_url(self) -> str:
        if not self.current_id:
            return ""
        return f"{API_BASE}/api/pdf/{self.current_id}/resume?v={self.preview_nonce}"

    @rx.var
    def cover_pdf_url(self) -> str:
        if not self.current_id:
            return ""
        return f"{API_BASE}/api/pdf/{self.current_id}/cover?v={self.preview_nonce}"

    def load_dashboard(self):
        master = MasterResume.load(settings.master_resume)
        self.tracks = master.tracks
        if not self.track:
            self.track = master.tracks[0] if master.tracks else ""
        if not self.provider:
            self.provider = settings.llm_provider
            self.refresh_models()
        self.applications = [
            AppRow(
                id=a.id,
                company=a.company or "(unknown)",
                role_title=a.role_title or "(unknown)",
                track=a.track,
                stage=a.stage,
                outcome=a.outcome,
                coverage=f"{a.coverage:.0%}" if a.coverage is not None else "-",
                ats=f"{a.ats_score}%" if a.ats_score is not None else "-",
                created=a.created_at.strftime("%Y-%m-%d"),
                model=a.llm_model or a.llm_provider or "-",
            )
            for a in service.list_applications()
        ]
        outcomes = [a.outcome for a in self.applications]
        self.stat_total = len(outcomes)
        self.stat_waiting = outcomes.count(Outcome.APPLIED)
        self.stat_interviews = sum(
            outcomes.count(o) for o in (Outcome.SCREEN, Outcome.INTERVIEW, Outcome.OFFER)
        )
        self.stat_rejected = outcomes.count(Outcome.REJECTED)

    @rx.event
    def set_outcome(self, application_id: str, value: str):
        service.update_application(application_id, outcome=value)
        self.load_dashboard()

    # -- quick scan ---------------------------------------------------------

    @rx.event(background=True)
    async def run_scan(self):
        async with self:
            if not self.jd_text.strip():
                self.error = "Paste the job description to scan it."
                return
            self.scanning, self.scan_done, self.error = True, False, ""
            text, provider, model = self.jd_text, self.provider, self.model
        try:
            result = await asyncio.to_thread(scan.quick_scan, text, provider, model)
        except Exception as exc:
            async with self:
                self.scanning = False
                self.error = f"{type(exc).__name__}: {exc}"
            return
        async with self:
            self.scanning, self.scan_done = False, True
            self.scan_match = result["match"]
            self.scan_verdict = result["verdict"]
            self.scan_reason = result["reason"]
            self.scan_strengths = result["strengths"]
            self.scan_gaps = result["gaps"]
            self.scan_tools_have = result["tools_have"]
            self.scan_tools_missing = result["tools_missing"]
            self.scan_ats_ceiling = result["ats_ceiling"]
            self.company = self.company or result["company"]
            self.role_title = self.role_title or result["role_title"]

    @rx.var
    def scan_colour(self) -> str:
        return "green" if self.scan_match >= 70 else "amber" if self.scan_match >= 50 else "red"

    @rx.var
    def ats_colour(self) -> str:
        return "green" if self.ats_score >= 70 else "amber" if self.ats_score >= 50 else "red"

    # -- model picker -------------------------------------------------------

    @rx.event
    def set_provider(self, value: str):
        self.provider = value
        self.model = ""
        self.refresh_models()

    @rx.event
    def set_model(self, value: str):
        self.model = value

    @rx.event
    def refresh_models(self):
        """Ask the endpoint what it is actually serving. An unreachable endpoint leaves
        the list empty and says so rather than offering models that do not exist."""
        self.models = available_models(self.provider or None)
        self.models_error = (
            "" if self.models else f"no models listed by {self.provider or settings.llm_provider}"
        )
        if self.models and self.model not in self.models:
            configured = settings.lmstudio_model if self.provider == "lmstudio" else ""
            self.model = configured if configured in self.models else self.models[0]

    # -- delete -------------------------------------------------------------

    @rx.event
    def ask_delete(self, application_id: str):
        self.pending_delete = application_id

    @rx.event
    def cancel_delete(self):
        self.pending_delete = ""

    @rx.event
    def confirm_delete(self):
        """Deletes the row, its draft history, its PDFs and its graph checkpoints."""
        if self.pending_delete:
            service.delete_application(self.pending_delete)
            self.pending_delete = ""
            self.load_dashboard()

    # -- new application ----------------------------------------------------

    @rx.event(background=True)
    async def create(self):
        async with self:
            if not self.jd_url and not self.jd_text.strip():
                self.error = "Give a job posting URL or paste the description."
                return
            self.busy, self.error = True, ""
            self.status = "Fetching posting and tailoring..."
            track, url, text = self.track, self.jd_url, self.jd_text
            company, role = self.company, self.role_title
            provider, model = self.provider, self.model

        try:
            record = await asyncio.to_thread(
                service.create_application,
                track=track,
                jd_url=url,
                jd_text=text,
                company=company,
                role_title=role,
                llm_provider=provider,
                llm_model=model,
            )
            payload = await asyncio.to_thread(service.start, record.id)
        except Exception as exc:  # surfaced in the UI rather than only in the log
            async with self:
                self.busy, self.status = False, ""
                self.error = f"{type(exc).__name__}: {exc}"
            return

        async with self:
            self.busy, self.status = False, ""
            self.current_id = record.id
            self._apply_gate(payload)
        return rx.redirect(f"/review/{record.id}")

    # -- review -------------------------------------------------------------

    def load_review(self):
        self.current_id = self.app_id
        self.error = ""
        if not self.current_id:
            return
        payload = service.pending_gate(self.current_id)
        if payload is None:
            state = service.snapshot(self.current_id)
            self.gate = "complete" if state.get("stage") == "complete" else ""
            return
        self._apply_gate(payload)

    def load_detail(self):
        self.current_id = self.app_id
        record = service.get_application(self.current_id) if self.current_id else None
        self.jd_text = record.jd_text if record else ""

    def _apply_gate(self, payload: dict[str, Any] | None):
        self.preview_nonce += 1
        if payload is None:
            self.gate = "complete"
            return

        self.gate = payload.get("kind", "")
        self.violations = list(payload.get("violations") or [])
        self.notes = list(payload.get("notes") or [])

        if self.gate == "resume":
            draft = payload.get("draft") or {}
            self._draft = draft
            self.pages = int(payload.get("pages") or 0)
            self.trim_log = list(payload.get("trim_log") or [])
            coverage = payload.get("coverage") or {}
            self.coverage_summary = coverage.get("summary", "")
            self.coverage_missing = list(coverage.get("missing") or [])[:25]
            estimate = payload.get("ats") or {}
            self.ats_score = int(estimate.get("score", -1))
            self.ats_parts = "  ".join(
                f"{k} {v}%" for k, v in (estimate.get("parts") or {}).items()
            )
            self.ats_tools_missing = list(estimate.get("tools_missing") or [])
            self.ats_ceiling = int(estimate.get("ceiling", -1))
            self.ats_phrases_missing = list(estimate.get("phrases_missing") or [])
            parse = payload.get("parse") or {}
            self.parse_ok = bool(parse.get("ok", True))
            self.spacing_risk = bool(parse.get("spacing_risk"))
            self._load_editors(draft)

        elif self.gate == "cover":
            cover = payload.get("cover") or {}
            self._cover = cover
            self.cover_paragraphs = [
                EditParagraph(index=i, text=text)
                for i, text in enumerate(cover.get("paragraphs") or [])
            ]

    def _load_editors(self, draft: dict[str, Any]):
        master = MasterResume.load(settings.master_resume)
        pool = master.bullet_pool(draft.get("track", self.track))

        self.objective = draft.get("objective", "")
        self.header_role = draft.get("role", "")
        self.roles, self.bullets = [], []

        for section in ("professional", "additional"):
            for role in draft.get(section) or []:
                self.roles.append(
                    EditRole(
                        id=role["id"], title=role["title"], org=role["org"],
                        date_range=role["date_range"], section=section,
                    )
                )
                for index, text in enumerate(role.get("bullets") or []):
                    bullet_id = role["bullet_ids"][index]
                    self.bullets.append(
                        EditBullet(
                            key=f"{role['id']}:{index}",
                            role_id=role["id"],
                            index=index,
                            bullet_id=bullet_id,
                            text=text,
                            source=pool[bullet_id].text if bullet_id in pool else "",
                        )
                    )

        self.skill_groups = [
            EditSkillGroup(key=g["key"], label=g["label"], joined=", ".join(g["entries"]))
            for g in draft.get("skills") or []
        ]
        self.certifications = [c["name"] for c in draft.get("certifications") or []]

    # -- editing ------------------------------------------------------------

    @rx.event
    def set_bullet(self, key: str, value: str):
        for bullet in self.bullets:
            if bullet.key == key:
                bullet.text = value
                break

    @rx.event
    def set_skill_group(self, key: str, value: str):
        for group in self.skill_groups:
            if group.key == key:
                group.joined = value
                break

    @rx.event
    def set_paragraph(self, index: int, value: str):
        for paragraph in self.cover_paragraphs:
            if paragraph.index == index:
                paragraph.text = value
                break

    def _collected_draft(self) -> dict[str, Any]:
        draft = json.loads(json.dumps(self._draft))
        draft["objective"] = self.objective
        draft["role"] = self.header_role

        edits: dict[str, list[str]] = {}
        for bullet in self.bullets:
            edits.setdefault(bullet.role_id, []).append(bullet.text)
        for section in ("professional", "additional"):
            for role in draft.get(section) or []:
                if role["id"] in edits:
                    role["bullets"] = edits[role["id"]]

        by_key = {g.key: g for g in self.skill_groups}
        for group in draft.get("skills") or []:
            if group["key"] in by_key:
                group["entries"] = [
                    s.strip() for s in by_key[group["key"]].joined.split(",") if s.strip()
                ]
        return draft

    def _collected_cover(self) -> dict[str, Any]:
        cover = json.loads(json.dumps(self._cover))
        cover["paragraphs"] = [p.text for p in self.cover_paragraphs]
        return cover

    # -- decisions ----------------------------------------------------------

    @rx.event(background=True)
    async def decide(self, action: str):
        async with self:
            self.busy, self.error = True, ""
            self.status = {
                "approve": "Approving...",
                "revise": "Recompiling your edits...",
                "reject": "Regenerating...",
            }.get(action, "Working...")
            decision: dict[str, Any] = {"action": action}
            if self.gate == "resume":
                if action in ("revise", "approve"):
                    decision["draft"] = self._collected_draft()
            elif self.gate == "cover" and action in ("revise", "approve"):
                decision["cover"] = self._collected_cover()
            if action == "reject":
                decision["feedback"] = self.feedback
            if self.provider:
                decision["llm_provider"] = self.provider
            if self.model:
                decision["llm_model"] = self.model
            app_id = self.current_id

        try:
            payload = await asyncio.to_thread(service.resume, app_id, decision)
        except Exception as exc:
            async with self:
                self.busy, self.status = False, ""
                self.error = f"{type(exc).__name__}: {exc}"
            return

        async with self:
            self.busy, self.status, self.feedback = False, "", ""
            self._apply_gate(payload)
