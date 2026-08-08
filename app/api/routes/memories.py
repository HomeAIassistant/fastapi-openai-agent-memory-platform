"""Long-term memory write and search routes.

Every route here requires the configured bearer token. Writes go through
`propose_memory` (validate -> policy -> embed -> store); there is no
unrestricted write path.
"""

from fastapi import APIRouter, Depends, HTTPException, Query

from ...memory.models import (
    MemoryCreateRequest,
    MemoryRecord,
    MemorySearchRequest,
    MemorySearchResult,
)
from ...memory.policy import WritePolicy
from ...memory.writer import MemoryValidationError, propose_memory
from ...security.auth import authorize
from ...stores.database import MemoryRepository
from ...stores.embeddings import EmbeddingProvider
from ..dependencies import get_embeddings, get_policy, get_repository

router = APIRouter(dependencies=[Depends(authorize)], tags=["memories"])


@router.post("/memories", response_model=MemoryRecord, status_code=201)
def create_memory(
    payload: MemoryCreateRequest,
    policy: WritePolicy = Depends(get_policy),
    repository: MemoryRepository = Depends(get_repository),
    embeddings: EmbeddingProvider = Depends(get_embeddings),
) -> MemoryRecord:
    """Validate, policy-check, embed, and store one proposed memory."""

    try:
        return propose_memory(
            payload, policy=policy, repository=repository, embeddings=embeddings
        )
    except MemoryValidationError as exc:
        raise HTTPException(
            status_code=422, detail={"code": "policy_rejected", "message": str(exc)}
        ) from exc


@router.get("/memories/{memory_id}", response_model=MemoryRecord)
def get_memory(
    memory_id: str,
    tenant_id: str = Query(..., min_length=1, max_length=128),
    project_id: str = Query(..., min_length=1, max_length=128),
    repository: MemoryRepository = Depends(get_repository),
) -> MemoryRecord:
    """Fetch one memory, scoped to the caller's tenant/project."""

    record = repository.get(memory_id, tenant_id=tenant_id, project_id=project_id)
    if record is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "not_found", "message": f"memory '{memory_id}' not found"},
        )
    return record


@router.post("/memories/search", response_model=list[MemorySearchResult])
def search_memories(
    payload: MemorySearchRequest,
    repository: MemoryRepository = Depends(get_repository),
    embeddings: EmbeddingProvider = Depends(get_embeddings),
) -> list[MemorySearchResult]:
    """Embed the query and return the top-k scoped results by similarity."""

    query_embedding = embeddings.embed(payload.query)
    hits = repository.search(
        scope=payload.scope,
        query_embedding=query_embedding,
        top_k=payload.top_k,
        types=payload.types,
        include_pending=payload.include_pending,
    )
    return [MemorySearchResult(memory=record, score=score) for record, score in hits]
