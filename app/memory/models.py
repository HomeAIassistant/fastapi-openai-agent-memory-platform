"""Pydantic contract for long-term memory records and API payloads.

Mirrors the memory record contract in `plan.md`: every record carries scope,
provenance, confidence, lifecycle, and policy fields. Nothing here accepts
free-form ACL or scope decisions from a caller-supplied field beyond the
identifiers themselves; type/sensitivity legality is enforced separately by
`app.memory.policy`.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

WriteStatus = Literal["approved", "pending_approval"]


class MemoryScope(BaseModel):
    """Tenant/project/user/agent scope a memory belongs to or a search targets."""

    tenant_id: str = Field(min_length=1, max_length=128)
    project_id: str = Field(min_length=1, max_length=128)
    user_id: str | None = Field(default=None, max_length=128)
    agent_id: str | None = Field(default=None, max_length=128)


class MemoryProvenance(BaseModel):
    """Where a proposed memory came from."""

    source_type: str = Field(min_length=1, max_length=64)
    run_id: str | None = Field(default=None, max_length=128)
    source_id: str | None = Field(default=None, max_length=256)


class MemoryCreateRequest(BaseModel):
    """Caller-supplied proposal for one long-term memory."""

    type: str = Field(min_length=1, max_length=64)
    scope: MemoryScope
    content: str = Field(min_length=1, max_length=8000)
    provenance: MemoryProvenance
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    sensitivity: str = Field(default="internal", max_length=32)
    expires_at: datetime | None = None
    # Accepted and stored for forward compatibility; superseding the
    # referenced memory is not yet implemented (plan.md Phase C).
    supersedes: str | None = Field(default=None, max_length=64)


class MemoryRecord(BaseModel):
    """A stored long-term memory, including server-assigned fields."""

    memory_id: str
    type: str
    scope: MemoryScope
    content: str
    provenance: MemoryProvenance
    confidence: float
    created_at: datetime
    expires_at: datetime | None
    supersedes: str | None
    sensitivity: str
    write_status: WriteStatus


class MemorySearchRequest(BaseModel):
    """A scoped semantic search over approved (by default) memories."""

    scope: MemoryScope
    query: str = Field(min_length=1, max_length=2000)
    top_k: int = Field(default=10, ge=1, le=50)
    types: list[str] | None = None
    # Only set by callers explicitly authorized to see unapproved memories.
    include_pending: bool = False


class MemorySearchResult(BaseModel):
    """One ranked search hit."""

    memory: MemoryRecord
    score: float
