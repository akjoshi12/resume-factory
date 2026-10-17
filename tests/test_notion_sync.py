"""Notion sync, against an in-memory fake that speaks the same five calls as the client.

Covers the failures that would quietly corrupt data or spam Notion: a second page for
the same application, a Notion-owned field overwritten by a push, a failed push that is
lost instead of retried, a renamed property that writes to nothing, and a dry run that
touches the network. No NOTION_TOKEN is needed, and none is ever sent.
"""

from __future__ import annotations

import copy
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx
import pytest
from sqlmodel import select

from rfactory import service
from rfactory.config import settings
from rfactory.db import session as db_session
from rfactory.db.models import Application, NotionOutbox, Outcome
from rfactory.sync import notion_sync
from rfactory.sync.notion_sync import NotionError, NotionSchemaError

DB = "db-test"
NOW = datetime(2026, 10, 17, 10, 0, tzinfo=timezone.utc)


@pytest.fixture
def fresh(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "db_path", tmp_path / "rfactory.db")
    monkeypatch.setattr(settings, "out_dir", tmp_path / "out")
    monkeypatch.setattr(settings, "notion_token", "")
    monkeypatch.setattr(settings, "notion_db_id", "")
    monkeypatch.setattr(service, "_app", None)
    monkeypatch.setattr(db_session, "_engine", None)
    monkeypatch.setattr(db_session, "_engine_path", None)
    return tmp_path


class FakeNotion:
    """Stores what it is sent, so tests can see exactly which properties were written."""

    def __init__(self) -> None:
        self.schema: dict[str, Any] = {
            name: {"type": kind} for name, kind in notion_sync.SCHEMA.items()
        }
        self.pages: dict[str, dict[str, Any]] = {}
        self.created: list[dict[str, Any]] = []
        self.updated: list[tuple[str, dict[str, Any]]] = []
        self.fail_next: list[Exception] = []  # raised by the next write, in order
        self.clock = NOW

    def _maybe_fail(self) -> None:
        if self.fail_next:
            raise self.fail_next.pop(0)

    def retrieve_database(self, database_id: str) -> dict[str, Any]:
        return {"properties": self.schema}

    def update_database(self, database_id: str, properties: dict[str, Any]) -> dict[str, Any]:
        self.schema.update(properties)
        return {}

    def query_database(
        self, database_id: str, filter: dict[str, Any] | None = None
    ) -> list[dict[str, Any]]:
        pages = list(self.pages.values())
        if filter and filter.get("property") == "RF ID":
            wanted = filter["rich_text"]["equals"]
            pages = [p for p in pages if _plain(p["properties"].get("RF ID")) == wanted]
        if filter and "timestamp" in filter:
            since = filter["last_edited_time"]["on_or_after"]
            pages = [p for p in pages if p["last_edited_time"] >= since]
        return [_as_notion_returns(p) for p in pages]

    def create_page(self, database_id: str, properties: dict[str, Any]) -> dict[str, Any]:
        self._maybe_fail()
        self.created.append(properties)
        page_id = f"page-{len(self.pages) + 1}"
        self.pages[page_id] = {
            "id": page_id,
            "properties": copy.deepcopy(properties),
            "last_edited_time": self.clock.isoformat(),
        }
        return {"id": page_id}

    def update_page(self, page_id: str, properties: dict[str, Any]) -> dict[str, Any]:
        self._maybe_fail()
        self.updated.append((page_id, properties))
        self.pages[page_id]["properties"].update(copy.deepcopy(properties))
        self.pages[page_id]["last_edited_time"] = self.clock.isoformat()
        return {"id": page_id}

    def edit_in_notion(self, page_id: str, properties: dict[str, Any], when: datetime) -> None:
        """A change made by hand in Notion, at a given time."""
        self.pages[page_id]["properties"].update(copy.deepcopy(properties))
        self.pages[page_id]["last_edited_time"] = when.isoformat()


def _plain(prop: dict[str, Any] | None) -> str:
    items = (prop or {}).get("rich_text") or (prop or {}).get("title") or []
    return "".join(item.get("text", {}).get("content", "") for item in items)


def _as_notion_returns(page: dict[str, Any]) -> dict[str, Any]:
    """Real Notion responses add plain_text to rich text; the sync code reads that."""
    out = copy.deepcopy(page)
    for prop in out["properties"].values():
        for key in ("rich_text", "title"):
            for item in prop.get(key, []):
                item["plain_text"] = item.get("text", {}).get("content", "")
    return out


def _approved(company: str = "Acme", track: str = "ai_eng", referral: bool = False) -> str:
    record = service.create_application(
        track=track, company=company, role_title="Data Analyst", jd_url="https://jobs.test/1"
    )
    service.update_application(record.id, applied_at=NOW, referral=referral)
    return record.id


def _application(application_id: str) -> Application:
    with db_session.get_session() as session:
        return session.get(Application, application_id)


def test_pushing_twice_leaves_one_page(fresh):
    app_id = _approved()
    notion = FakeNotion()

    notion_sync.push_application(app_id, notion, DB, now=NOW)
    notion_sync.push_application(app_id, notion, DB, now=NOW)

    assert len(notion.pages) == 1
    assert len(notion.created) == 1
    assert _application(app_id).notion_page_id == "page-1"


def test_a_page_that_exists_without_a_stored_id_is_found_not_duplicated(fresh):
    app_id = _approved()
    notion = FakeNotion()
    notion_sync.push_application(app_id, notion, DB, now=NOW)
    with db_session.get_session() as session:
        session.get(Application, app_id).notion_page_id = None
        session.commit()

    notion_sync.push_application(app_id, notion, DB, now=NOW)

    assert len(notion.pages) == 1
    assert _application(app_id).notion_page_id == "page-1"


def test_notion_owned_fields_survive_a_push(fresh):
    app_id = _approved(referral=True)
    notion = FakeNotion()
    notion_sync.push_application(app_id, notion, DB, now=NOW)
    created = notion.created[0]
    assert created["Status"] == {"select": {"name": "Applied"}}
    assert created["Outcome"] == {"select": {"name": notion_sync.DASH}}
    assert created["Source"] == {"select": {"name": "Referral"}}

    # Hand edits in Notion, then a local edit that forces an update.
    page_id = _application(app_id).notion_page_id
    notion.edit_in_notion(
        page_id,
        {"Outcome": {"select": {"name": "Rejected"}}, "Status": {"select": {"name": "Closed"}}},
        NOW + timedelta(hours=1),
    )
    with db_session.get_session() as session:
        session.get(Application, app_id).company = "Acme Renamed"
        session.commit()

    # Pull first, as every run does: a push rewrites the page's last_edited_time, so an
    # edit that has not been read yet would no longer be visible afterwards.
    assert notion_sync.pull_changes(notion, DB, now=NOW + timedelta(hours=2)) == 1
    assert _application(app_id).outcome == Outcome.REJECTED

    notion.clock = NOW + timedelta(hours=2)
    notion_sync.push_application(app_id, notion, DB, now=NOW + timedelta(hours=2))
    _, sent = notion.updated[-1]
    assert "Status" not in sent and "Outcome" not in sent
    assert set(sent) <= {"Position", "Company", "Posting URL", "Resume", "Date Applied",
                         "Source", "RF ID", "Resume Version"}
    assert notion.pages[page_id]["properties"]["Outcome"] == {"select": {"name": "Rejected"}}
    assert _application(app_id).company == "Acme Renamed"


def test_failed_push_is_queued_and_retried_after_its_backoff(fresh):
    app_id = _approved()
    notion = FakeNotion()
    notion.fail_next = [NotionError("rate limited", status=429, retry_after=120)]

    assert notion_sync.push_pending(notion, DB, now=NOW) == (0, 1)
    with db_session.get_session() as session:
        row = session.exec(select(NotionOutbox)).one()
    assert row.application_id == app_id
    assert row.attempts == 1
    assert row.next_try_at.replace(tzinfo=timezone.utc) == NOW + timedelta(seconds=120)
    assert notion.pages == {}

    # Not due yet: nothing is attempted.
    assert notion_sync.drain_outbox(notion, DB, now=NOW + timedelta(seconds=60)) == (0, 0)
    assert notion.pages == {}

    # Due, and Notion is healthy again.
    assert notion_sync.drain_outbox(notion, DB, now=NOW + timedelta(seconds=121)) == (1, 0)
    assert len(notion.pages) == 1
    with db_session.get_session() as session:
        assert session.exec(select(NotionOutbox)).all() == []


def test_backoff_doubles_is_capped_and_honours_retry_after():
    assert notion_sync.backoff_seconds(1) == 60
    assert notion_sync.backoff_seconds(2) == 120
    assert notion_sync.backoff_seconds(3) == 240
    assert notion_sync.backoff_seconds(30) == notion_sync.MAX_BACKOFF_SECONDS
    assert notion_sync.backoff_seconds(1, retry_after=500) == 500


def test_pull_compares_at_minute_granularity(fresh):
    # Notion rounds last_edited_time down to the minute. A sync at 10:00:45 must still
    # pick up an edit Notion stamps 10:00:00; an edit stamped 09:59 is from before it.
    same_minute = _approved(company="Same")
    earlier = _approved(company="Earlier")
    notion = FakeNotion()
    notion_sync.push_application(same_minute, notion, DB, now=NOW)
    notion_sync.push_application(earlier, notion, DB, now=NOW)
    with db_session.get_session() as session:
        for app_id in (same_minute, earlier):
            session.get(Application, app_id).notion_synced_at = NOW + timedelta(seconds=45)
        session.commit()
    notion.edit_in_notion(
        _application(same_minute).notion_page_id,
        {"Outcome": {"select": {"name": "Rejected"}}},
        NOW,
    )
    notion.edit_in_notion(
        _application(earlier).notion_page_id,
        {"Outcome": {"select": {"name": "Ghosted"}}},
        NOW - timedelta(minutes=1),
    )

    assert notion_sync.pull_changes(notion, DB, now=NOW + timedelta(minutes=2)) == 1
    assert _application(same_minute).outcome == Outcome.REJECTED
    assert _application(earlier).outcome == Outcome.NOT_SENT


def test_a_blank_notion_notes_does_not_wipe_local_notes(fresh):
    app_id = _approved()
    notion = FakeNotion()
    notion_sync.push_application(app_id, notion, DB, now=NOW)
    with db_session.get_session() as session:
        session.get(Application, app_id).notes = "local thoughts"
        session.commit()
    notion.edit_in_notion(
        _application(app_id).notion_page_id,
        {"Status": {"select": {"name": "Interviewing"}}},
        NOW + timedelta(minutes=5),
    )

    assert notion_sync.pull_changes(notion, DB, now=NOW + timedelta(minutes=10)) == 1
    assert _application(app_id).notes == "local thoughts"
    assert _application(app_id).outcome == Outcome.INTERVIEW


def test_a_renamed_property_fails_loudly_and_names_it(fresh):
    _approved()
    notion = FakeNotion()
    notion.schema["Date Applied "] = notion.schema.pop("Date Applied")

    with pytest.raises(NotionSchemaError, match="'Date Applied'"):
        notion_sync.ensure_schema(notion, DB)
    assert notion.created == []


def test_a_dry_run_makes_no_network_calls(fresh, monkeypatch, capsys):
    _approved()

    def no_network(*_args: Any, **_kwargs: Any) -> None:
        raise AssertionError("network call during dry-run")

    monkeypatch.setattr(httpx.Client, "request", no_network)

    assert notion_sync.main(["push", "--dry-run"]) == 0
    assert notion_sync.main(["sync", "--dry-run"]) == 0
    out = capsys.readouterr().out
    assert "look up by RF ID, create if absent" in out
    assert "pull:" in out


def test_approval_push_never_raises_and_queues_when_notion_is_down(fresh, monkeypatch):
    app_id = _approved()
    monkeypatch.setattr(settings, "notion_token", "token-not-sent")
    monkeypatch.setattr(settings, "notion_db_id", DB)

    def offline(*_args: Any, **_kwargs: Any) -> None:
        raise httpx.ConnectError("offline")

    monkeypatch.setattr(httpx.Client, "request", offline)

    notion_sync.push_after_approval(app_id)  # must not raise

    with db_session.get_session() as session:
        row = session.exec(select(NotionOutbox)).one()
    assert row.application_id == app_id
    assert row.attempts == 1
    assert "token-not-sent" not in (row.last_error or "")
