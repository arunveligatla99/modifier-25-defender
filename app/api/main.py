"""FastAPI application entry point.

Mounts the routes from :mod:`app.api.routes` (POST /analyze) plus the
healthz liveness probe.
"""

from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.api.routes import router as analyze_router
from app.infra.settings import get_settings


def create_app() -> FastAPI:
    """Build and return the FastAPI application instance."""
    settings = get_settings()
    logging.basicConfig(level=settings.log_level)

    app = FastAPI(
        title="Modifier 25 Defender",
        version=__version__,
        description=(
            "A documentation defensibility tool for podiatry coders, built on "
            "the JARALL Standard, with citation-first synthesis and an "
            "independent compliance guard."
        ),
    )

    # CORS allowlist. Localhost dev origins are always allowed. Ngrok
    # tunnels (free + paid) are allowed via regex so demo recordings
    # against a tunneled UI work without recompiling the image. Set
    # CORS_EXTRA_ORIGINS in the environment to add explicit origins for
    # custom deployments.
    extra = [o.strip() for o in (settings.cors_extra_origins or "").split(",") if o.strip()]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://localhost:3000", *extra],
        allow_origin_regex=r"https?://[a-z0-9-]+\.ngrok(-free)?\.(app|dev|io)$",
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["*"],
    )

    @app.get("/healthz")
    async def healthz() -> dict[str, str]:
        """Liveness probe for docker-compose and CI."""
        return {"status": "ok", "version": __version__}

    app.include_router(analyze_router)
    return app


app = create_app()
