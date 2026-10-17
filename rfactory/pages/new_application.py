from __future__ import annotations

import reflex as rx

from rfactory.pages.common import labelled, model_picker, shell
from rfactory.state.app_state import AppState


def _list(title: str, items: rx.Var, colour: str) -> rx.Component:
    return rx.vstack(
        rx.text(title, size="2", weight="bold", color=f"var(--{colour}-11)"),
        rx.foreach(items, lambda item: rx.text("• " + item, size="2")),
        spacing="1",
        align="start",
        flex="1",
        min_width="16em",
    )


def _scan_card() -> rx.Component:
    return rx.card(
        rx.vstack(
            rx.hstack(
                rx.heading(AppState.scan_match.to_string() + "% fit", size="7",
                           color="var(--" + AppState.scan_colour + "-11)"),
                rx.badge(AppState.scan_verdict, color_scheme=AppState.scan_colour, size="3"),
                align="center",
                spacing="3",
            ),
            rx.text("Fit is a recruiter-style judgement. The best ATS score a resume built "
                    "from your experience can reach for this posting is about "
                    + AppState.scan_ats_ceiling.to_string() + "%; the generated resume "
                    "is scored against the same formula.", size="1", color="var(--gray-11)"),
            rx.text(AppState.scan_reason, size="2"),
            rx.hstack(
                _list("Strengths", AppState.scan_strengths, "green"),
                _list("Gaps", AppState.scan_gaps, "red"),
                width="100%",
                spacing="4",
                wrap="wrap",
                align="start",
            ),
            rx.cond(
                AppState.scan_tools_missing.length() > 0,
                rx.text("Tools asked for that you have not used: "
                        + AppState.scan_tools_missing.join(", "),
                        size="1", color="var(--gray-11)"),
            ),
            rx.cond(
                AppState.scan_tools_have.length() > 0,
                rx.text("Tools you have: " + AppState.scan_tools_have.join(", "),
                        size="1", color="var(--gray-11)"),
            ),
            spacing="3",
            align="start",
            width="100%",
        ),
        width="100%",
    )


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
        rx.hstack(
            rx.button("Quick scan: should I apply?", on_click=AppState.run_scan,
                      loading=AppState.scanning, variant="soft", size="3"),
            rx.button("Generate resume", on_click=AppState.create, loading=AppState.busy, size="3"),
            spacing="3",
        ),
        rx.cond(AppState.scan_done, _scan_card()),
        title="New application",
    )
