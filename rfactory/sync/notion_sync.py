"""Mirror approved applications into a Notion database, and pull Notion-owned edits back.

Ownership is split by field, and the split is the point. SQLite owns what the app knows
(company, role, track, applied date, referral). Notion owns what happens after you send
it (status, outcome, notes, next action). Push never writes a Notion-owned field once the
page exists, and pull never writes a SQLite-owned one, so neither side clobbers the other.

Nothing here raises into the app. A failed push is parked in NotionOutbox and retried
with backoff; `sync` drains it. A missing or retyped Notion property is the one loud
error, because retrying cannot fix a renamed column.

    python -m rfactory.sync.notion_sync push [--dry-run]
    python -m rfactory.sync.notion_sync sync [--dry-run]
    python -m rfactory.sync.notion_sync init-schema [--apply] [--dry-run]
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Protocol

import httpx
from sqlmodel import select

from rfactory.config import settings
from rfactory.db.models import Application, DraftVersion, NotionOutbox, Outcome
from rfactory.db.session import get_session, init_db

logger = logging.getLogger(__name__)

DASH = "—"  # Notion's "no outcome yet" option in the Outcome select
TRACK_TO_RESUME = {"ai_eng": "AI Engineer", "data_eng": "Data Engineering"}
OUTCOME_FROM_NOTION = {
    "Offer": Outcome.OFFER,
    "Rejected": Outcome.REJECTED,
    "Ghosted": Outcome.GHOSTED,
    "Withdrawn": Outcome.WITHDRAWN,
}

# Property name -> Notion type. Every run checks the database against this first, so a
# renamed or retyped column fails here instead of writing to nothing.
SCHEMA: dict[str, str] = {
    "Position": "title",
    "Company": "rich_text",
    "Posting URL": "url",
    "Resume": "select",
    "Date Applied": "date",
    "Source": "select",
    "Status": "select",
    "Outcome": "select",
    "Next Action": "rich_text",
    "Next Action Date": "date",
    "RF ID": "rich_text",
    "Resume Version": "number",
    "Notes": "rich_text",
}
# The three properties added on top of the original database, for init-schema.
NEW_PROPERTIES: dict[str, dict[str, Any]] = {
    "RF ID": {"rich_text": {}},
    "Resume Version": {"number": {"format": "number"}},
    "Notes": {"rich_text": {}},
}

BASE_BACKOFF_SECONDS = 60
MAX_BACKOFF_SECONDS = 3600
MIN_REQUEST_INTERVAL = 1 / 3  # Notion allows an average of three requests a second


class NotionError(Exception):
    def __init__(
        self, message: str, *, status: int | None = None, retry_after: float | None = None
    ) -> None:
        super().__init__(message)
        self.status = status
        self.retry_after = retry_after


class NotionSchemaError(NotionError):
    """The database lacks a property the code expects. Retrying cannot fix it."""


class NotionAPI(Protocol):
    def retrieve_database(self, database_id: str) -> dict[str, Any]: ...

    def update_database(self, database_id: str, properties: dict[str, Any]) -> dict[str, Any]: ...

    def query_database(
        self, database_id: str, filter: dict[str, Any] | None = None
    ) -> list[dict[str, Any]]: ...

    def create_page(self, database_id: str, properties: dict[str, Any]) -> dict[str, Any]: ...

    def update_page(self, page_id: str, properties: dict[str, Any]) -> dict[str, Any]: ...


class NotionHTTP:
    """The real client. httpx is already a dependency, so there is no SDK to add."""

    def __init__(self, token: str, *, timeout: float = 30.0) -> None:
        self._http = httpx.Client(
            base_url="https://api.notion.com/v1",
            headers={"Authorization": f"Bearer {token}", "Notion-Version": "2022-06-28"},
            timeout=timeout,
        )
        self._last_request = 0.0

    def close(self) -> None:
        self._http.close()

    def _call(self, method: str, path: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
        # Throttled here, so no caller can exceed the rate limit.
        wait = MIN_REQUEST_INTERVAL - (time.monotonic() - self._last_request)
        if wait > 0:
            time.sleep(wait)
        try:
            response = self._http.request(method, path, json=body)
        except httpx.HTTPError as exc:
            raise NotionError(f"{method} {path}: network error ({type(exc).__name__})") from None
        finally:
            self._last_request = time.monotonic()
        if response.status_code == 429:
            raise NotionError(
                f"{method} {path}: rate limited",
                status=429,
                retry_after=_seconds(response.headers.get("Retry-After")),
            )
        if response.status_code >= 400:
            detail = response.json().get("message", "") if response.content else ""
            raise NotionError(
                f"{method} {path}: HTTP {response.status_code} {detail}".rstrip(),
                status=response.status_code,
            )
        return response.json()

    def retrieve_database(self, database_id: str) -> dict[str, Any]:
        return self._call("GET", f"/databases/{database_id}")

    def update_database(self, database_id: str, properties: dict[str, Any]) -> dict[str, Any]:
        return self._call("PATCH", f"/databases/{database_id}", {"properties": properties})

    def query_database(
        self, database_id: str, filter: dict[str, Any] | None = None
    ) -> list[dict[str, Any]]:
        pages: list[dict[str, Any]] = []
        cursor: str | None = None
        while True:
            body: dict[str, Any] = {"page_size": 100}
            if filter:
                body["filter"] = filter
            if cursor:
                body["start_cursor"] = cursor
            data = self._call("POST", f"/databases/{database_id}/query", body)
            pages.extend(data["results"])
            cursor = data.get("next_cursor")
            if not data.get("has_more") or not cursor:
                return pages

    def create_page(self, database_id: str, properties: dict[str, Any]) -> dict[str, Any]:
        return self._call(
            "POST", "/pages", {"parent": {"database_id": database_id}, "properties": properties}
        )

    def update_page(self, page_id: str, properties: dict[str, Any]) -> dict[str, Any]:
        return self._call("PATCH", f"/pages/{page_id}", {"properties": properties})


def _seconds(header: str | None) -> float | None:
    try:
        return float(header) if header is not None else None
    except ValueError:
        return None


# -- property encoding and decoding -------------------------------------------


def _title(text: str) -> dict[str, Any]:
    return {"title": [{"text": {"content": text}}]}


def _rich(text: str) -> dict[str, Any]:
    return {"rich_text": [{"text": {"content": text}}] if text else []}


def _select(name: str) -> dict[str, Any]:
    return {"select": {"name": name}}


def _read_text(prop: dict[str, Any] | None) -> str:
    items = (prop or {}).get("title") or (prop or {}).get("rich_text") or []
    return "".join(item.get("plain_text", "") for item in items)


def _read_select(prop: dict[str, Any] | None) -> str | None:
    return ((prop or {}).get("select") or {}).get("name")


def _read_date(prop: dict[str, Any] | None) -> str | None:
    return ((prop or {}).get("date") or {}).get("start")


# -- time ---------------------------------------------------------------------


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _utc(value: datetime) -> datetime:
    # SQLite hands datetimes back naive; everything written here is UTC.
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value


def _floor_minute(value: datetime) -> datetime:
    # Notion's last_edited_time is rounded down to the minute, so comparisons against it
    # have to be made at minute granularity or an edit in the same minute as a sync is lost.
    return _utc(value).replace(second=0, microsecond=0)


# -- ownership ----------------------------------------------------------------


def _resume_version(application_id: str) -> int | None:
    with get_session() as session:
        versions = session.exec(
            select(DraftVersion.version).where(
                DraftVersion.application_id == application_id, DraftVersion.kind == "resume"
            )
        ).all()
    return max(versions, default=None)


def _sqlite_owned(app: Application, resume_version: int | None) -> dict[str, Any]:
    """The properties SQLite is the source of truth for. Safe to send on every update."""
    props: dict[str, Any] = {
        "Position": _title(app.role_title or app.company or "Untitled role"),
        "Company": _rich(app.company),
        "Posting URL": {"url": app.jd_url or None},
        "Date Applied": {"date": {"start": _utc(app.applied_at).astimezone().date().isoformat()}},
        "RF ID": _rich(app.id),
    }
    if resume := TRACK_TO_RESUME.get(app.track):
        props["Resume"] = _select(resume)
    else:
        logger.warning("track %r has no Notion Resume option; leaving Resume unset", app.track)
    if resume_version is not None:
        props["Resume Version"] = {"number": resume_version}
    if app.referral:
        props["Source"] = _select("Referral")  # when not a referral, Source is never touched
    return props


def _needs_push(app: Application) -> bool:
    if app.applied_at is None:
        return False  # not approved: existing not_sent rows are never backfilled
    if app.notion_page_id is None or app.notion_synced_at is None:
        return True
    return _utc(app.updated_at) > _utc(app.notion_synced_at)


# -- schema -------------------------------------------------------------------


def ensure_schema(client: NotionAPI, database_id: str) -> None:
    props = client.retrieve_database(database_id).get("properties", {})
    for name, kind in SCHEMA.items():
        if name not in props:
            raise NotionSchemaError(
                f"Notion database has no property {name!r} (expected {kind}). "
                "Restore the name, or run init-schema if it is one of the new properties."
            )
        actual = props[name].get("type")
        if actual != kind:
            raise NotionSchemaError(
                f"Notion property {name!r} is {actual}, expected {kind}"
            )


def init_schema(client: NotionAPI, database_id: str) -> list[str]:
    existing = client.retrieve_database(database_id).get("properties", {})
    missing = {name: spec for name, spec in NEW_PROPERTIES.items() if name not in existing}
    if missing:
        client.update_database(database_id, missing)
    return sorted(missing)


# -- push ---------------------------------------------------------------------


def _record_page(application_id: str, page_id: str, now: datetime) -> None:
    # Bookkeeping is written directly, not through update_application: that would bump
    # updated_at and make every run look like a local edit.
    with get_session() as session:
        app = session.get(Application, application_id)
        if app is None:
            return
        app.notion_page_id = page_id
        app.notion_synced_at = now
        session.add(app)
        session.commit()


def _clear_outbox(application_id: str) -> None:
    with get_session() as session:
        for row in session.exec(
            select(NotionOutbox).where(NotionOutbox.application_id == application_id)
        ).all():
            session.delete(row)
        session.commit()


def push_application(
    application_id: str, client: NotionAPI, database_id: str, *, now: datetime
) -> None:
    """Create or update one application's page. Raises NotionError; see _push_or_queue."""
    with get_session() as session:
        app = session.get(Application, application_id)
        if app is None or app.applied_at is None:
            return
        page_id = app.notion_page_id
    props = _sqlite_owned(app, _resume_version(application_id))

    if page_id is None:
        # Look before creating: a page can exist without us having stored its id, and a
        # second page for the same application is the duplicate this must prevent.
        matches = client.query_database(
            database_id, {"property": "RF ID", "rich_text": {"equals": application_id}}
        )
        if not matches:
            # Status and Outcome are Notion-owned after this: sent on creation only.
            page = client.create_page(
                database_id,
                {**props, "Status": _select("Applied"), "Outcome": _select(DASH)},
            )
            _record_page(application_id, page["id"], now)
            _clear_outbox(application_id)
            return
        page_id = matches[0]["id"]

    client.update_page(page_id, props)
    _record_page(application_id, page_id, now)
    _clear_outbox(application_id)


def backoff_seconds(attempts: int, retry_after: float | None = None) -> float:
    """Exponential and capped, and never sooner than Notion asked for."""
    delay = min(MAX_BACKOFF_SECONDS, BASE_BACKOFF_SECONDS * 2 ** (attempts - 1))
    return max(delay, retry_after or 0.0)


def _record_failure(application_id: str, error: Exception, *, now: datetime) -> None:
    with get_session() as session:
        row = session.exec(
            select(NotionOutbox).where(NotionOutbox.application_id == application_id)
        ).first()
        if row is None:
            row = NotionOutbox(application_id=application_id)
            session.add(row)
        row.attempts += 1
        row.last_error = str(error)[:500]
        retry_after = getattr(error, "retry_after", None)
        row.next_try_at = now + timedelta(seconds=backoff_seconds(row.attempts, retry_after))
        session.commit()


def _push_or_queue(
    application_id: str, client: NotionAPI, database_id: str, *, now: datetime
) -> bool:
    try:
        push_application(application_id, client, database_id, now=now)
    except NotionSchemaError:
        raise
    except NotionError as exc:
        logger.warning("Notion push for %s failed, queued: %s", application_id, exc)
        _record_failure(application_id, exc, now=now)
        return False
    return True


def push_pending(client: NotionAPI, database_id: str, *, now: datetime) -> tuple[int, int]:
    """Push every application that needs it. Returns (pushed, queued). Applications already
    waiting in the outbox are left to drain_outbox, so their backoff is honoured."""
    with get_session() as session:
        queued_ids = {row.application_id for row in session.exec(select(NotionOutbox))}
        ids = [
            app.id
            for app in session.exec(select(Application))
            if _needs_push(app) and app.id not in queued_ids
        ]
    pushed = sum(_push_or_queue(i, client, database_id, now=now) for i in ids)
    return pushed, len(ids) - pushed


def drain_outbox(client: NotionAPI, database_id: str, *, now: datetime) -> tuple[int, int]:
    """Retry queued pushes that are due. Returns (sent, still_failing)."""
    with get_session() as session:
        due = [
            row.application_id
            for row in session.exec(select(NotionOutbox))
            if _utc(row.next_try_at) <= now
        ]
    sent = sum(_push_or_queue(i, client, database_id, now=now) for i in due)
    return sent, len(due) - sent


def push_after_approval(application_id: str) -> None:
    """Called by the app right after a resume approval. Never raises into the caller: a
    failed push is queued in NotionOutbox, and a schema mismatch is logged as an error."""
    if not (settings.notion_token and settings.notion_db_id):
        logger.debug("Notion sync not configured; skipping %s", application_id)
        return
    now = _now()
    client = NotionHTTP(settings.notion_token)
    try:
        ensure_schema(client, settings.notion_db_id)
        _push_or_queue(application_id, client, settings.notion_db_id, now=now)
    except NotionSchemaError as exc:
        logger.error("Notion sync not run: %s", exc)
    except Exception as exc:  # any other failure is queued, never raised into the UI
        logger.warning("Notion push for %s failed, queued: %s", application_id, exc)
        _record_failure(application_id, exc, now=now)
    finally:
        client.close()


# -- pull ---------------------------------------------------------------------


def pull_changes(client: NotionAPI, database_id: str, *, now: datetime) -> int:
    """Read Notion-owned fields for pages edited since their application was last synced.
    Returns the number of applications updated."""
    with get_session() as session:
        linked = list(
            session.exec(select(Application).where(Application.notion_page_id.is_not(None)))
        )
    if not linked:
        return 0
    if any(app.notion_synced_at is None for app in linked):
        since = None
    else:
        since = min(_floor_minute(app.notion_synced_at) for app in linked if app.notion_synced_at)
    query = (
        None
        if since is None
        else {
            "timestamp": "last_edited_time",
            "last_edited_time": {"on_or_after": since.isoformat()},
        }
    )
    pages = client.query_database(database_id, query)
    return sum(_apply_page(page, now=now) for page in pages)


def _apply_page(page: dict[str, Any], *, now: datetime) -> bool:
    props = page.get("properties", {})
    application_id = _read_text(props.get("RF ID"))
    if not application_id:
        return False
    edited = datetime.fromisoformat(page["last_edited_time"])
    with get_session() as session:
        app = session.get(Application, application_id)
        if app is None:
            return False
        # Applied again when it is the same minute: re-applying Notion's values is harmless.
        if app.notion_synced_at is not None and edited < _floor_minute(app.notion_synced_at):
            return False

        outcome_name = _read_select(props.get("Outcome"))
        status = _read_select(props.get("Status"))
        if outcome_name in OUTCOME_FROM_NOTION:
            app.outcome = OUTCOME_FROM_NOTION[outcome_name]
        elif status == "Interviewing":
            app.outcome = Outcome.INTERVIEW
        elif status == "Closed":
            logger.warning(
                "%s is Closed in Notion with no Outcome; leaving outcome as %s",
                application_id,
                app.outcome,
            )
        # A blank Notion Notes never wipes local notes; clearing them in Notion is not synced.
        notion_notes = _read_text(props.get("Notes"))
        if notion_notes or not app.notes:
            app.notes = notion_notes
        app.next_action = _read_text(props.get("Next Action"))
        app.next_action_date = _read_date(props.get("Next Action Date"))
        app.notion_synced_at = now
        session.add(app)
        session.commit()
    return True


# -- dry run ------------------------------------------------------------------


def plan(command: str) -> list[str]:
    """What a real run would do, read from SQLite alone. Makes no network calls."""
    lines: list[str] = []
    with get_session() as session:
        apps = [app for app in session.exec(select(Application)) if _needs_push(app)]
        queued = list(session.exec(select(NotionOutbox)))
    for app in apps:
        action = "update" if app.notion_page_id else "look up by RF ID, create if absent"
        props = _sqlite_owned(app, _resume_version(app.id))
        lines.append(f"push {app.id} ({app.company} / {app.role_title}): {action}")
        lines.append(f"  properties: {json.dumps(props, ensure_ascii=False)}")
    for row in queued:
        lines.append(
            f"outbox {row.application_id}: {row.attempts} failed attempt(s), "
            f"next try {_utc(row.next_try_at).isoformat()}"
        )
    if command == "sync":
        lines.append("pull: Notion-owned fields since last sync (needs Notion; skipped)")
    return lines


# -- CLI ----------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m rfactory.sync.notion_sync")
    parser.add_argument("command", choices=["push", "sync", "init-schema"])
    parser.add_argument("--dry-run", action="store_true", help="print the plan; no network")
    parser.add_argument("--apply", action="store_true", help="init-schema: PATCH the database")
    args = parser.parse_args(argv)
    init_db()

    if args.command == "init-schema":
        if args.dry_run or not args.apply:
            for name in sorted(NEW_PROPERTIES):
                print(f"would add property {name!r} ({', '.join(NEW_PROPERTIES[name])})")
            if not args.apply:
                print("pass --apply to PATCH the database")
            return 0
    elif args.dry_run:
        for line in plan(args.command):
            print(line)
        return 0

    if not (settings.notion_token and settings.notion_db_id):
        print("NOTION_TOKEN and NOTION_DB_ID must be set (.env or environment)", file=sys.stderr)
        return 2

    client = NotionHTTP(settings.notion_token)
    try:
        database_id = settings.notion_db_id
        if args.command == "init-schema":
            added = init_schema(client, database_id)
            print(f"added: {', '.join(added) or 'nothing (already present)'}")
            return 0
        now = _now()
        ensure_schema(client, database_id)
        # Pull before any write, so Notion edits are read before a push can hide them.
        print(f"pull: updated {pull_changes(client, database_id, now=now)}")
        if args.command == "sync":
            sent, failing = drain_outbox(client, database_id, now=now)
            print(f"outbox: sent {sent}, still failing {failing}")
        pushed, queued = push_pending(client, database_id, now=now)
        print(f"push: sent {pushed}, queued {queued}")
        return 0
    except NotionError as exc:
        print(f"notion sync failed: {exc}", file=sys.stderr)
        return 1
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
