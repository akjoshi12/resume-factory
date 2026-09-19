from __future__ import annotations

import reflex as rx

from rfactory.pages.common import labelled, model_picker, shell
from rfactory.state.app_state import AppState


def page() -> rx.Component:
    return shell(
        rx.text(
            "Paste a posting URL if you have one. Most job boards block automated "
            "fetching, so the description box is the reliable path.",
            color="var(--gray-11)",
            size="2",
        ),
        labelled("Track", rx.select(AppState.tracks, value=AppState.track,
                                    on_change=AppState.set_track, width="20em")),
        model_picker(),
        labelled("Job posting URL (optional)",
                 rx.input(value=AppState.jd_url, on_change=AppState.set_jd_url,
                          placeholder="https://...", width="100%")),
        rx.hstack(
            labelled("Company (optional)",
                     rx.input(value=AppState.company, on_change=AppState.set_company,
                              width="100%")),
            labelled("Role title (optional)",
                     rx.input(value=AppState.role_title, on_change=AppState.set_role_title,
                              width="100%")),
            width="100%",
            spacing="4",
        ),
        labelled("Job description",
                 rx.text_area(value=AppState.jd_text, on_change=AppState.set_jd_text,
                              rows="16", width="100%")),
        rx.button("Generate resume", on_click=AppState.create, loading=AppState.busy, size="3"),
        title="New application",
    )
