"""FastAPI application factory for Yantronix Scraper API."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router
from app.core.config import settings

def create_app() -> FastAPI:
    """Create and configure the FastAPI application instance."""

    application = FastAPI(title=settings.app_name)
    application.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.allowed_origins),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    application.include_router(router)

    @application.get("/health", tags=["System"])
    def health_check() -> dict[str, str]:
        """Lightweight endpoint for cron-job.org to keep the server awake."""
        return {"status": "ok"}

    return application


app = create_app()
