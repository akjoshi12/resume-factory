from __future__ import annotations

import reflex as rx

from rfactory.pages.common import shell
from rfactory.state.app_state import AppState


def page() -> rx.Component:
    return shell(
        rx.tabs.root(
            rx.tabs.list(
                rx.tabs.trigger("Resume", value="resume"),
                rx.tabs.trigger("Cover letter", value="cover"),
                rx.tabs.trigger("Job description", value="jd"),
            ),
            rx.tabs.content(
                rx.el.iframe(src=AppState.resume_pdf_url, width="100%", height="85vh"),
                value="resume",
            ),
            rx.tabs.content(
                rx.el.iframe(src=AppState.cover_pdf_url, width="100%", height="85vh"),
                value="cover",
            ),
            rx.tabs.content(
                rx.text(AppState.jd_text, white_space="pre-wrap", size="2"),
                value="jd",
            ),
            default_value="resume",
            width="100%",
        ),
        rx.link("Back to dashboard", href="/"),
        title="Application",
    )
