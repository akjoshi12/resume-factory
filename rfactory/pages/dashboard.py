from __future__ import annotations

import reflex as rx

from rfactory.pages.common import shell
from rfactory.state.app_state import AppRow, AppState

STAGE_COLOURS = {
    "new": "gray",
    "resume_review": "amber",
    "cover_review": "amber",
    "complete": "green",
    "abandoned": "gray",
}


def _row(app: AppRow) -> rx.Component:
    return rx.table.row(
        rx.table.cell(rx.link(app.company, href=f"/app/{app.id}")),
        rx.table.cell(app.role_title),
        rx.table.cell(rx.badge(app.track, variant="soft")),
        rx.table.cell(rx.badge(app.stage, color_scheme="gray")),
        rx.table.cell(app.outcome),
        rx.table.cell(app.coverage),
        rx.table.cell(app.model),
        rx.table.cell(app.created),
        rx.table.cell(
            rx.hstack(
                rx.link("Review", href=f"/review/{app.id}"),
                rx.button(
                    "Delete",
                    on_click=lambda: AppState.ask_delete(app.id),
                    variant="ghost",
                    color_scheme="red",
                    size="1",
                ),
                spacing="3",
            )
        ),
    )


def _delete_dialog() -> rx.Component:
    return rx.alert_dialog.root(
        rx.alert_dialog.content(
            rx.alert_dialog.title("Delete this application?"),
            rx.alert_dialog.description(
                "This removes the record, its draft history, its generated PDFs and its "
                "graph checkpoints. It cannot be undone."
            ),
            rx.hstack(
                rx.alert_dialog.cancel(
                    rx.button("Cancel", variant="soft", on_click=AppState.cancel_delete)
                ),
                rx.alert_dialog.action(
                    rx.button("Delete", color_scheme="red", on_click=AppState.confirm_delete)
                ),
                spacing="3",
                justify="end",
                margin_top="1em",
            ),
        ),
        open=AppState.pending_delete != "",
    )


def page() -> rx.Component:
    return shell(
        _delete_dialog(),
        rx.cond(
            AppState.applications.length() == 0,
            rx.vstack(
                rx.text("No applications yet."),
                rx.link(rx.button("Start one"), href="/new"),
                spacing="3",
                padding_y="2em",
            ),
            rx.table.root(
                rx.table.header(
                    rx.table.row(
                        *[
                            rx.table.column_header_cell(h)
                            for h in (
                                "Company", "Role", "Track", "Stage",
                                "Outcome", "Coverage", "Model", "Created", "",
                            )
                        ]
                    )
                ),
                rx.table.body(rx.foreach(AppState.applications, _row)),
                width="100%",
            ),
        ),
    )
