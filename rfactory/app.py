from __future__ import annotations

import reflex as rx
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import FileResponse, JSONResponse, Response
from starlette.routing import Route

from rfactory import service
from rfactory.pages import dashboard, detail, new_application, review
from rfactory.state.app_state import AppState


async def serve_pdf(request: Request) -> Response:
    """Generated PDFs live under out/, not in assets/, so they are served from the
    backend rather than copied into the static build on every regeneration."""
    app_id = request.path_params["app_id"]
    kind = request.path_params["kind"]
    if kind not in ("resume", "cover"):
        return JSONResponse({"detail": "unknown artifact"}, status_code=404)
    path = service.artifact_path(app_id, kind)
    if path is None:
        return JSONResponse({"detail": "not generated yet"}, status_code=404)
    return FileResponse(path, media_type="application/pdf")


# Reflex 0.9 mounts an extra Starlette app rather than exposing a FastAPI instance.
api = Starlette(routes=[Route("/api/pdf/{app_id}/{kind}", serve_pdf, methods=["GET"])])

app = rx.App(api_transformer=api)

app.add_page(dashboard.page, route="/", title="Resume Factory", on_load=AppState.load_dashboard)
app.add_page(
    new_application.page, route="/new", title="New application", on_load=AppState.load_dashboard
)
app.add_page(review.page, route="/review/[app_id]", title="Review", on_load=AppState.load_review)
app.add_page(detail.page, route="/app/[app_id]", title="Application", on_load=AppState.load_detail)
