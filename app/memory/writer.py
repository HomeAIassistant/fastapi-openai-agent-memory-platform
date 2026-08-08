"""Deterministic long-term-memory write path: validate -> policy -> store.

There is no unrestricted `remember(anything)` path. Every proposal is
type/sensitivity-validated against the configured policy, assigned a
server-controlled id, timestamp, and write_status, embedded, and only then
persisted.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from ..stores.database import MemoryRepository
from ..stores.embeddings import EmbeddingProvider
from .models import MemoryCreateRequest, MemoryRecord
from .policy import PolicyConfigError, WritePolicy


class MemoryValidationError(ValueError):
    """Raised when a proposed memory violates the write policy."""


def propose_memory(
    request: MemoryCreateRequest,
    *,
    policy: WritePolicy,
    repository: MemoryRepository,
    embeddings: EmbeddingProvider,
) -> MemoryRecord:
    """Validate, policy-check, embed, and durably store one proposed memory."""

    try:
        policy.validate_type(request.type)
        policy.validate_sensitivity(request.sensitivity)
    except PolicyConfigError as exc:
        raise MemoryValidationError(str(exc)) from exc

    record = MemoryRecord(
        memory_id=f"mem_{uuid.uuid4().hex}",
        type=request.type,
        scope=request.scope,
        content=request.content,
        provenance=request.provenance,
        confidence=request.confidence,
        created_at=datetime.now(UTC),
        expires_at=request.expires_at,
        supersedes=request.supersedes,
        sensitivity=request.sensitivity,
        write_status=policy.resolve_write_status(request.sensitivity),
    )
    vector = embeddings.embed(request.content)
    repository.create(record, embedding=vector)
    return record
