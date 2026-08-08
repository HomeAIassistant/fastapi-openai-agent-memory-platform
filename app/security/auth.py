"""Bearer-token authentication for protected memory routes."""

import secrets

from fastapi import Header, HTTPException, Request

from ..core.settings import Settings


def authorize(
    request: Request,
    authorization: str | None = Header(default=None),
) -> None:
    """Require the configured bearer token for protected API routes."""

    settings: Settings = request.app.state.settings
    expected = f"Bearer {settings.memory_api_token.get_secret_value()}"
    if authorization is None or not secrets.compare_digest(authorization, expected):
        raise HTTPException(
            status_code=401,
            detail={"code": "unauthorized", "message": "Invalid bearer token."},
            headers={"WWW-Authenticate": "Bearer"},
        )
