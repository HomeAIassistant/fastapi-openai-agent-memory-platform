"""FastAPI application factory and router registration."""

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from ..core.lifecycle import lifespan
from ..core.settings import Settings, get_settings
from .routes import memories, system


def create_app(settings: Settings | None = None) -> FastAPI:
    """Create the configured FastAPI application."""

    current = settings or get_settings()
    logging.basicConfig(
        level=current.app_log_level.upper(),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    application = FastAPI(
        title=current.app_name,
        version=current.app_version,
        lifespan=lifespan,
    )
    application.state.settings = current

    if current.parsed_cors_origins:
        application.add_middleware(
            CORSMiddleware,
            allow_origins=current.parsed_cors_origins,
            allow_credentials=False,
            allow_methods=["GET", "POST"],
            allow_headers=["Authorization", "Content-Type"],
        )

    application.include_router(system.router)
    application.include_router(memories.router)
    return application
