from __future__ import annotations

import reflex as rx

from rfactory.pages.common import labelled, model_picker, shell
from rfactory.state.app_state import (
    LOCKED_NOTE,
    AppState,
    EditBullet,
    EditParagraph,
    EditRole,
    EditSkillGroup,
)


def _bullet(bullet: EditBullet) -> rx.Component:
    return rx.vstack(
        rx.text_area(
            value=bullet.text,
            on_change=lambda value: AppState.set_bullet(bullet.key, value),
            rows="3",
            width="100%",
        ),
        rx.cond(
            bullet.source != bullet.text,
            rx.text(
                f"source ({bullet.bullet_id}): " + bullet.source,
                size="1",
                color="var(--gray-10)",
            ),
        ),
        spacing="1",
        width="100%",
        align="start",
    )


def _role(role: EditRole) -> rx.Component:
    return rx.card(
        rx.vstack(
            rx.hstack(
                rx.text(role.title, weight="bold"),
                rx.text(role.org, color="var(--gray-11)"),
                rx.spacer(),
                rx.text(role.date_range, color="var(--gray-11)", size="2"),
                width="100%",
                align="center",
            ),
            rx.foreach(
                AppState.bullets.to(list[EditBullet]),
                lambda b: rx.cond(b.role_id == role.id, _bullet(b)),
            ),
            spacing="2",
            width="100%",
            align="start",
        ),
        width="100%",
    )


def _skill_group(group: EditSkillGroup) -> rx.Component:
    return labelled(
        group.label,
        rx.input(
            value=group.joined,
            on_change=lambda value: AppState.set_skill_group(group.key, value),
            width="100%",
        ),
    )


def _signals() -> rx.Component:
    return rx.card(
        rx.vstack(
            rx.hstack(
                rx.badge(f"{AppState.pages} page", color_scheme=rx.cond(AppState.over_length, "red", "green")),
                rx.badge(AppState.coverage_summary, variant="soft"),
                rx.cond(AppState.parse_ok, rx.badge("parses", color_scheme="green"),
                        rx.badge("PARSE FAILURE", color_scheme="red")),
                rx.cond(AppState.spacing_risk,
                        rx.badge("spacing risk", color_scheme="amber", variant="soft")),
                spacing="2",
                wrap="wrap",
            ),
            rx.cond(
                AppState.has_violations,
                rx.callout(
                    rx.vstack(
                        rx.text("Unverified claims - these appear in the draft but not in your "
                                "approved bullets. Fix or delete them before sending.",
                                weight="bold", size="2"),
                        rx.foreach(AppState.violations, lambda v: rx.text(v, size="1")),
                        spacing="1", align="start",
                    ),
                    icon="triangle_alert", color_scheme="red", width="100%",
                ),
            ),
            rx.cond(
                AppState.coverage_missing.length() > 0,
                rx.text("JD terms not on the resume: " + AppState.coverage_missing.join(", "),
                        size="1", color="var(--gray-11)"),
            ),
            rx.cond(
                AppState.trim_log.length() > 0,
                rx.vstack(
                    rx.text("Trimmed to fit one page:", size="1", weight="bold"),
                    rx.foreach(AppState.trim_log,
                               lambda t: rx.text(t, size="1", color="var(--gray-10)")),
                    spacing="0", align="start",
                ),
            ),
            spacing="3", width="100%", align="start",
        ),
        width="100%",
    )


def _decisions() -> rx.Component:
    return rx.vstack(
        rx.card(model_picker(compact=True), width="100%"),
        rx.hstack(
            rx.button("Save edits and recompile", on_click=lambda: AppState.decide("revise"),
                      variant="soft", loading=AppState.busy),
            rx.button("Approve", on_click=lambda: AppState.decide("approve"),
                      color_scheme="green", loading=AppState.busy),
            spacing="3",
        ),
        labelled(
            "Reject and regenerate - say what was wrong",
            rx.text_area(value=AppState.feedback, on_change=AppState.set_feedback,
                         placeholder="too generic; lead with the data quality work; "
                                     "drop the Pinecone bullet",
                         rows="3", width="100%"),
        ),
        rx.button("Reject and regenerate", on_click=lambda: AppState.decide("reject"),
                  color_scheme="red", variant="soft", loading=AppState.busy),
        spacing="3", width="100%", align="start",
    )


def _resume_gate() -> rx.Component:
    return rx.hstack(
        rx.vstack(
            _signals(),
            rx.text(LOCKED_NOTE, size="1", color="var(--gray-10)"),
            labelled("Header role", rx.input(value=AppState.header_role,
                                             on_change=AppState.set_header_role, width="100%")),
            labelled("Objective", rx.text_area(value=AppState.objective,
                                               on_change=AppState.set_objective,
                                               rows="4", width="100%")),
            rx.heading("Experience", size="3"),
            rx.foreach(AppState.roles, _role),
            rx.heading("Skills", size="3"),
            rx.foreach(AppState.skill_groups, _skill_group),
            rx.heading("Certifications", size="3"),
            rx.foreach(AppState.certifications, lambda c: rx.text(c, size="2")),
            _decisions(),
            width="50%", spacing="4", align="start",
        ),
        rx.box(
            rx.el.iframe(src=AppState.resume_pdf_url, width="100%", height="90vh",
                         style={"border": "1px solid var(--gray-5)"}),
            width="50%", position="sticky", top="1em",
        ),
        width="100%", align="start", spacing="4",
    )


def _paragraph(paragraph: EditParagraph) -> rx.Component:
    return rx.text_area(
        value=paragraph.text,
        on_change=lambda value: AppState.set_paragraph(paragraph.index, value),
        rows="6", width="100%",
    )


def _cover_gate() -> rx.Component:
    return rx.hstack(
        rx.vstack(
            rx.cond(
                AppState.has_violations,
                rx.callout(
                    rx.vstack(
                        rx.text("Claims in the letter that the resume does not support:",
                                weight="bold", size="2"),
                        rx.foreach(AppState.violations, lambda v: rx.text(v, size="1")),
                        spacing="1", align="start",
                    ),
                    icon="triangle_alert", color_scheme="red", width="100%",
                ),
            ),
            rx.cond(
                AppState.has_notes,
                rx.callout(
                    rx.vstack(
                        rx.text("Worth a read before sending - the letter uses words from the "
                                "posting that are not on your resume:", weight="bold", size="2"),
                        rx.foreach(AppState.notes, lambda n: rx.text(n, size="1")),
                        spacing="1", align="start",
                    ),
                    icon="info", color_scheme="amber", width="100%",
                ),
            ),
            rx.heading("Cover letter", size="3"),
            rx.foreach(AppState.cover_paragraphs, _paragraph),
            _decisions(),
            width="50%", spacing="4", align="start",
        ),
        rx.box(
            rx.el.iframe(src=AppState.cover_pdf_url, width="100%", height="90vh",
                         style={"border": "1px solid var(--gray-5)"}),
            width="50%", position="sticky", top="1em",
        ),
        width="100%", align="start", spacing="4",
    )


def page() -> rx.Component:
    return shell(
        rx.match(
            AppState.gate,
            ("resume", _resume_gate()),
            ("cover", _cover_gate()),
            (
                "complete",
                rx.vstack(
                    rx.heading("Done", size="4"),
                    rx.hstack(
                        rx.link(rx.button("Download resume"), href=AppState.resume_pdf_url,
                                is_external=True),
                        rx.link(rx.button("Download cover letter", variant="soft"),
                                href=AppState.cover_pdf_url, is_external=True),
                        spacing="3",
                    ),
                    rx.link("Back to dashboard", href="/"),
                    spacing="4", align="start",
                ),
            ),
            rx.text("Nothing pending for this application."),
        ),
        title="Review",
    )
