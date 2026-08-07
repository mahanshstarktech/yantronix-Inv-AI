"""FastAPI application factory for Yantronix Scraper API."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router
from app.core.config import settings

def create_app() -> FastAPI:
    """Create and configure the FastAPI application instance."""

    application = FastAPI(title=settings.app_name)
    
    # Naye local ports ko explicitly allow karein
    allowed = list(settings.allowed_origins) + [
        "http://localhost:8081",
        "http://localhost:3000",
        "http://localhost:5173",
        "http://127.0.0.1:8081"
    ]
    
    application.add_middleware(
        CORSMiddleware,
        allow_origins=allowed,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    application.include_router(router)
    return application


app = create_app()