"""Central translation of domain errors to safe HTTP responses.

Registered once on the app in `app/api/factory.py` rather than caught
per-route, so a new route that calls `MemoryRepository`/`EmbeddingProvider`
or `propose_memory` gets the same safe `503`/`422` behavior automatically —
it cannot forget the `try`/`except` and leak a raw driver/HTTP exception to
a caller. See `AGENTS.md`'s error-handling rule.
"""

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from ..memory.writer import MemoryValidationError
from ..stores.database import MemoryRepositoryError
from ..stores.embeddings import EmbeddingProviderError


def _service_unavailable(code: str, exc: Exception) -> JSONResponse:
    """Build a 503 response carrying the safe message from a domain error."""

    return JSONResponse(
        status_code=503, content={"detail": {"code": code, "message": str(exc)}}
    )


def register_error_handlers(app: FastAPI) -> None:
    """Register handlers translating domain errors into safe HTTP responses."""

    @app.exception_handler(MemoryValidationError)
    async def _handle_validation_error(
        request: Request, exc: MemoryValidationError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content={"detail": {"code": "policy_rejected", "message": str(exc)}},
        )

    @app.exception_handler(EmbeddingProviderError)
    async def _handle_embedding_error(
        request: Request, exc: EmbeddingProviderError
    ) -> JSONResponse:
        return _service_unavailable("embedding_unavailable", exc)

    @app.exception_handler(MemoryRepositoryError)
    async def _handle_repository_error(
        request: Request, exc: MemoryRepositoryError
    ) -> JSONResponse:
        return _service_unavailable("storage_unavailable", exc)
