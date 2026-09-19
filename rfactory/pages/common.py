from __future__ import annotations

import reflex as rx

from rfactory.state.app_state import AppState


def shell(*children: rx.Component, title: str = "Resume Factory") -> rx.Component:
    return rx.vstack(
        rx.hstack(
            rx.heading(title, size="6"),
            rx.spacer(),
            rx.link("Dashboard", href="/"),
            rx.link("New application", href="/new"),
            width="100%",
            align="center",
            padding_y="0.75em",
            border_bottom="1px solid var(--gray-5)",
        ),
        rx.cond(
            AppState.error != "",
            rx.callout(AppState.error, icon="triangle_alert", color_scheme="red", width="100%"),
        ),
        rx.cond(
            AppState.busy,
            rx.hstack(rx.spinner(), rx.text(AppState.status), padding_y="0.5em"),
        ),
        *children,
        width="100%",
        max_width="1400px",
        margin="0 auto",
        padding="1em",
        spacing="4",
        align="start",
    )


def labelled(label: str, *children: rx.Component) -> rx.Component:
    return rx.vstack(
        rx.text(label, size="1", weight="bold", color="var(--gray-11)"),
        *children,
        spacing="1",
        width="100%",
        align="start",
    )


def model_picker(compact: bool = False) -> rx.Component:
    """Provider and model selection. Shown on the new-application form and again at
    each review gate, because the useful move is drafting on the local model and
    re-running the cover letter on something stronger."""
    return rx.vstack(
        rx.hstack(
            labelled(
                "Provider",
                rx.select(
                    AppState.providers,
                    value=AppState.provider,
                    on_change=AppState.set_provider,
                    width="100%",
                ),
            ),
            labelled(
                "Model",
                rx.cond(
                    AppState.models.length() > 0,
                    rx.select(
                        AppState.models,
                        value=AppState.model,
                        on_change=AppState.set_model,
                        width="100%",
                    ),
                    rx.input(
                        value=AppState.model,
                        on_change=AppState.set_model,
                        placeholder="model id",
                        width="100%",
                    ),
                ),
            ),
            rx.button(
                "Refresh",
                on_click=AppState.refresh_models,
                variant="soft",
                size="1",
                margin_top="1.4em",
            ),
            width="100%",
            spacing="3",
            align="start",
        ),
        rx.cond(
            AppState.models_error != "",
            rx.text(AppState.models_error, size="1", color="var(--amber-11)"),
        ),
        rx.cond(
            compact,
            rx.text(
                "Applies to every step after this one.",
                size="1",
                color="var(--gray-10)",
            ),
        ),
        width="100%",
        spacing="1",
        align="start",
    )
