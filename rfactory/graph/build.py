"""The application graph.

Two interrupt() gates, one SQLite checkpointer. The checkpointer is what makes the
review gates real: state survives a browser close, a restart, or a day's gap between
generating a resume and deciding whether to send it.

Loops in the graph, and why each is where it is:
  tailor -> verify_claims -> tailor      bounded by max_verify_retries, then surfaces
                                         the violations to the human rather than hiding
                                         them.
  render_resume -> trim -> render_resume deterministic trimming to one page; no model
                                         call, so iterating is cheap and cannot invent.
  review gates -> back upstream          rejection with free-text feedback re-enters
                                         tailoring or cover drafting.
"""

from __future__ import annotations

from pathlib import Path

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, StateGraph

from rfactory.config import settings
from rfactory.graph.nodes import cover as cover_nodes
from rfactory.graph.nodes import ingest as ingest_nodes
from rfactory.graph.nodes import produce as produce_nodes
from rfactory.graph.nodes import tailor as tailor_nodes
from rfactory.graph.state import GraphState


def build_graph() -> StateGraph:
    graph = StateGraph(GraphState)

    graph.add_node("ingest_jd", ingest_nodes.ingest_jd)
    graph.add_node("tailor", tailor_nodes.tailor)
    graph.add_node("verify_claims", tailor_nodes.verify_claims)
    graph.add_node("build_draft", tailor_nodes.build_draft)
    graph.add_node("render_resume", produce_nodes.render_resume)
    graph.add_node("trim", produce_nodes.trim)
    graph.add_node("score_resume", produce_nodes.score_resume)
    graph.add_node("review_resume", produce_nodes.review_resume)
    graph.add_node("draft_cover", cover_nodes.draft_cover)
    graph.add_node("render_cover", cover_nodes.render_cover)
    graph.add_node("review_cover", cover_nodes.review_cover)
    graph.add_node("finalize", cover_nodes.finalize)

    graph.add_edge(START, "ingest_jd")
    graph.add_edge("ingest_jd", "tailor")
    graph.add_edge("tailor", "verify_claims")
    graph.add_conditional_edges(
        "verify_claims", tailor_nodes.route_after_verify, ["tailor", "build_draft"]
    )
    graph.add_edge("build_draft", "render_resume")
    graph.add_conditional_edges(
        "render_resume", produce_nodes.route_after_render, ["trim", "score_resume"]
    )
    graph.add_edge("trim", "render_resume")
    graph.add_edge("score_resume", "review_resume")
    graph.add_conditional_edges(
        "review_resume",
        produce_nodes.route_after_review,
        ["tailor", "render_resume", "draft_cover"],
    )
    graph.add_edge("draft_cover", "render_cover")
    graph.add_conditional_edges(
        "review_cover",
        cover_nodes.route_after_cover_review,
        ["draft_cover", "render_cover", "finalize"],
    )
    graph.add_edge("render_cover", "review_cover")
    graph.add_edge("finalize", END)

    return graph


def checkpointer(db_path: Path | None = None) -> SqliteSaver:
    """Shares the application database, so graph state and the dashboard's rows live
    in one file that can be backed up as a unit."""
    import sqlite3

    path = db_path or settings.db_path
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(str(path), check_same_thread=False)
    return SqliteSaver(connection)


def compile_graph(saver: SqliteSaver | None = None):  # type: ignore[no-untyped-def]
    return build_graph().compile(checkpointer=saver or checkpointer())
