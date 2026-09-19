"""Shared isolation.

Two module-level caches outlive a test: the compiled graph in service, and the SQLModel
engine. Both are reset here so each test gets its own database and output directory.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from rfactory import service
from rfactory.config import settings
from rfactory.db import session as db_session
from rfactory.graph.nodes import cover as cover_nodes
from rfactory.graph.nodes import ingest as ingest_nodes
from rfactory.graph.nodes import tailor as tailor_nodes

sys.path.insert(0, str(Path(__file__).parent))


@pytest.fixture
def isolated(tmp_path, monkeypatch):
    from test_graph_smoke import StubProvider

    monkeypatch.setattr(settings, "db_path", tmp_path / "rfactory.db")
    monkeypatch.setattr(settings, "out_dir", tmp_path / "out")
    monkeypatch.setattr(service, "_app", None)
    monkeypatch.setattr(db_session, "_engine", None)
    monkeypatch.setattr(db_session, "_engine_path", None)

    provider = StubProvider()
    for module in (ingest_nodes, tailor_nodes, cover_nodes):
        monkeypatch.setattr(module, "get_provider", lambda *_, **__: provider)
    return provider
