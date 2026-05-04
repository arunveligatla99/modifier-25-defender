"""FastAPI application entry point.

Wires the LangGraph compiled graph behind ``POST /analyze``. The graph itself
is built incrementally as agents land (T148). For now this module exposes
``/healthz`` and a stub ``/analyze`` route that returns a structured 503 with
a guidance message until the graph is wired.
"""

from __future__ import annotations

import logging

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.infra.settings import get_settings
from app.schemas.api import DefenderRequest, DefenderResponse

logger = logging.getLogger(__name__)


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

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://localhost:3000"],
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
    )

    @app.get("/healthz")
    async def healthz() -> dict[str, str]:
        """Liveness probe for docker-compose and CI."""
        return {"status": "ok", "version": __version__}

    @app.post("/analyze", response_model=DefenderResponse)
    async def analyze(_request: DefenderRequest) -> DefenderResponse:
        """Score an encounter for Modifier 25 defensibility.

        Stub during scaffolding (Phase 2 Foundational); real wiring lands in
        T149 once the LangGraph orchestrator (T148) is built.
        """
        raise HTTPException(
            status_code=503,
            detail={
                "error": "not_implemented",
                "reason": (
                    "POST /analyze is wired in T149 (US1 wire-together). The schema "
                    "and validation are in place; the LangGraph orchestrator and "
                    "agents land via tasks.md before this route returns real "
                    "responses."
                ),
            },
        )

    return app


app = create_app()
