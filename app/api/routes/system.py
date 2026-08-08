"""Public liveness and readiness routes."""

from fastapi import APIRouter, Depends, HTTPException

from ...stores.database import MemoryRepository
from ..dependencies import get_repository

router = APIRouter()


@router.get("/health", tags=["system"])
def health() -> dict[str, str]:
    """Return process liveness without checking external dependencies."""

    return {"status": "healthy"}


@router.get("/ready", tags=["system"])
def ready(repository: MemoryRepository = Depends(get_repository)) -> dict[str, object]:
    """Return readiness based on a minimal database round trip."""

    database_ready = repository.health()
    payload = {
        "status": "ready" if database_ready else "not_ready",
        "database": database_ready,
    }
    if payload["status"] != "ready":
        raise HTTPException(status_code=503, detail=payload)
    return payload
