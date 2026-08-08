"""ASGI entry point for the memory service."""

from .api.factory import create_app

app = create_app()
