"""FastAPI app: the API at /api and the built frontend at / on one origin (spec §8)."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse, Response
from sqlalchemy import text

from app.api import auth as auth_api
from app.api import clock as clock_api
from app.api import invites as invites_api
from app.api import kiosk as kiosk_api
from app.api import me as me_api
from app.api import team as team_api
from app.api import reasons as reasons_api
from app.api import activity_log as activity_api
from app.api import kiosks as kiosks_api
from app.api import paper as paper_api
from app.api import md as md_api
from app.api import people as people_api
from app.api import privacy as privacy_api
from app.config import get_settings
from app.db import app_engine


# Every API router. The permissions test walks these to check each endpoint's roles.
ROUTERS = (auth_api.router, me_api.router, invites_api.router, kiosk_api.router, clock_api.router,
           team_api.router, reasons_api.router, activity_api.router, people_api.router, kiosks_api.router,
           paper_api.router, md_api.router, privacy_api.router)


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="Attendance", docs_url=None, redoc_url=None, openapi_url=None)
    for router in ROUTERS:
        app.include_router(router)

    @app.get("/api/health", include_in_schema=False)
    def health() -> dict:
        with app_engine().connect() as conn:
            conn.execute(text("SELECT 1"))
        return {"ok": True}

    @app.middleware("http")
    async def security_headers(request: Request, call_next):
        response: Response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("Referrer-Policy", "same-origin")
        response.headers.setdefault("X-Frame-Options", "DENY")
        if settings.cookie_secure:
            response.headers.setdefault("Strict-Transport-Security", "max-age=31536000")
        if request.url.path.startswith("/api/"):
            response.headers.setdefault("Cache-Control", "no-store")
        return response

    _mount_frontend(app, settings.frontend_dist)
    return app


def _mount_frontend(app: FastAPI, dist: str) -> None:
    """Serve the built React app. Any non-API path gets index.html (client-side routing)."""
    root = Path(dist).resolve() if dist else None
    if root is None or not (root / "index.html").is_file():
        return
    index = root / "index.html"

    @app.api_route("/api/{rest:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE"], include_in_schema=False)
    def api_not_found(rest: str) -> JSONResponse:
        return JSONResponse({"detail": {"code": "not_found", "message": "Not found."}}, status_code=404)

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str) -> FileResponse:
        candidate = (root / path).resolve()
        if path and candidate.is_file() and candidate.is_relative_to(root):
            # Vite puts content-hashed files in /assets: safe to cache for a year.
            cache = "public, max-age=31536000, immutable" if path.startswith("assets/") else "no-cache"
            return FileResponse(candidate, headers={"Cache-Control": cache})
        return FileResponse(index, headers={"Cache-Control": "no-cache"})


app = create_app()
