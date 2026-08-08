
git@github.com:HomeAIassistant/fastapi-openai-agent-memory-platform.git
the repo for Agent Memory Architecture is 
fastapi-openai-agent-memory-platform


# Agent Memory Architecture Recommendation

## Executive Decision

**Yes. Long-term agent memory, semantic retrieval, RAG indexing, embeddings, and knowledge retrieval should become a separate stateful repository/service.**

However, **not every kind of “memory” belongs in that new repository**. The framework should distinguish four different concerns:

- **Runtime/control state** → remains in `fastapi-openai-agents-runtime-framework`.
- **Conversation/session memory** → implemented in the runtime using the OpenAI Agents SDK `Session` abstraction.
- **Long-term agent memory + semantic retrieval + RAG indexes** → new repository/service.
- **Document parsing/chunk generation** → remains in `document-processing-platform`.

That produces a clean four-repository platform:

```text
HomeAIassistant/
├── fastapi-openai-agents-runtime-framework
│   └── Stateless/bounded agent execution + session adapter
│
├── fastapi-openai-agents-langfuse
│   └── Observability, traces, prompts, evaluation
│
├── document-processing-platform
│   └── Documents -> DocumentIR -> chunks/index-ready records
│
└── agent-memory-platform                 ← NEW
    └── Long-term memory + knowledge retrieval + RAG indexes
```

I would **not** call the new repository simply `rag`. RAG is only one capability. A name such as:

```text
HomeAIassistant/agent-memory-platform
```

is the strongest fit.

## What The Current Repositories Tell Us

The current runtime architecture is already moving in the right direction. Its `RuntimeStore` is explicitly described as a **durable SQLite control plane for idempotency, approvals, audit events, external operations, and resumable SDK state**. It should stay that way. Turning that SQLite database into a conversation database, vector store, knowledge store, memory store, and audit database would collapse several distinct trust and lifecycle boundaries. 

The runtime's `AgentRunContext` similarly carries runtime-specific dependencies—run identity, user identity, idempotency, tool profiles, protected secrets, the runtime store, and configuration hashes. That provides a natural place to inject a **memory client**, rather than embedding an entire memory database into the runtime. 

Your agent configuration is also suitably strict and currently limited to model, prompt, tools, and execution configuration. Memory should become another explicit policy-controlled agent capability rather than something every agent receives automatically. 

The standalone Langfuse repository is already a precedent for the correct architecture: **stateful infrastructure with an independent lifecycle is separated from the stateless execution runtime**.  The existing operational documentation likewise treats Langfuse and runtime as independent deployments with separate validation, lifecycle, backup, and recovery procedures. 

Most importantly, `document-processing-platform` already explicitly defines its own retrieval boundary:

> it ends at parsed elements, stable chunks, index-ready records, and index-publication events; retrieval applications own searching, ranking, answer generation, and citations.

That almost directly defines where the new memory/RAG service should begin. 

## The Four Memory Layers

### Runtime State

This is **not agent memory**.

Keep these in the runtime repository:

```text
idempotency
approvals
resumable RunState
external-operation reservations
audit records
scheduler/workflow execution state
```

Do not put embeddings, chat history, learned preferences, or document chunks in `RuntimeStore`.

### Session Memory

This means:

```text
User: What airport did we discuss?
Agent: KJRA.

[next request]

User: What radius were we using?
Agent: 3 NM.
```

The OpenAI Agents SDK now has a first-class `Session` protocol specifically for persistent conversational history. The runner reads prior history before the run and writes new user/assistant/tool items afterward. Available implementations include SQLite, async SQLite, Redis, SQLAlchemy/PostgreSQL, MongoDB, Dapr, OpenAI Conversations, and encrypted session wrappers. 

**This belongs in the runtime framework**, because it is part of execution semantics.

I would add:

```text
app/
└── runtime/
    └── sessions/
        ├── __init__.py
        ├── factory.py
        ├── policy.py
        └── schemas.py
```

And agent configuration:

```yaml
memory:
  session:
    enabled: true
    backend: sqlite
    max_items: 40
    ttl_seconds: 86400
```

For your current single-LXC V1, begin with a **separate session SQLite database** on the existing runtime writable volume.

For example:

```text
/data/runtime.db
/data/sessions.db
```

Do **not** mix the tables.

The SDK explicitly supports file-backed SQLite for persistent sessions, while Redis or SQLAlchemy/PostgreSQL are appropriate if the runtime later becomes multi-worker or distributed. 

### Long-Term Agent Memory

This is fundamentally different.

Examples:

```text
Dan prefers concise operational reports.

Hudson NOTAM checks normally use the waterfront profile.

A previous workflow failed because radius > 10 NM violates policy.

The board approved vendor X on 2026-07-30.

This procedure was corrected after a prior failure.
```

These memories can survive:

- sessions;
- agent restarts;
- container replacement;
- model changes;
- workflow changes;
- potentially years.

That belongs in **`agent-memory-platform`**.

### RAG / Knowledge Retrieval

RAG answers questions from external source material:

```text
What does the Master Deed say about alterations?

What does this loan agreement require?

What was decided in the July board minutes?
```

This should share the retrieval infrastructure of `agent-memory-platform`, but the underlying records remain distinguishable from agent-generated memories.

Conceptually:

```text
retrieval corpus
├── knowledge
│   ├── documents
│   ├── emails
│   ├── policies
│   └── meeting minutes
│
└── memory
    ├── facts
    ├── preferences
    ├── decisions
    ├── workflow outcomes
    └── learned procedures
```

**Knowledge and memory can share a search engine without becoming the same data type.**

## New `agent-memory-platform`

I recommend approximately:

```text
agent-memory-platform/
├── app/
│   ├── api/
│   │   └── routes/
│   │       ├── health.py
│   │       ├── memories.py
│   │       ├── retrieval.py
│   │       ├── indexes.py
│   │       └── admin.py
│   │
│   ├── memory/
│   │   ├── models.py
│   │   ├── policy.py
│   │   ├── writer.py
│   │   ├── consolidator.py
│   │   └── lifecycle.py
│   │
│   ├── retrieval/
│   │   ├── query.py
│   │   ├── search.py
│   │   ├── ranking.py
│   │   ├── filters.py
│   │   └── citations.py
│   │
│   ├── indexing/
│   │   ├── ingestion.py
│   │   ├── embeddings.py
│   │   ├── chunk_mapper.py
│   │   └── deduplication.py
│   │
│   ├── stores/
│   │   ├── metadata.py
│   │   └── vectors.py
│   │
│   ├── security/
│   └── settings.py
│
├── tests/
├── docs/
├── compose.yaml
├── Dockerfile
└── Makefile
```

## Memory Record Contract

Long-term memory should **never just be arbitrary text written by an agent**.

Use something like:

```yaml
memory_id: mem_...
type: preference

scope:
  tenant_id: home
  project_id: henley
  user_id: ...
  agent_id: ...

content: >
  User prefers operational summaries with explicit next actions.

provenance:
  source_type: agent_run
  run_id: ...
  source_id: ...

confidence: 0.92

lifecycle:
  created_at: ...
  expires_at: null
  supersedes: null

policy:
  sensitivity: internal
  write_status: approved
```

Critical attributes are:

**provenance, scope, confidence, lifecycle, and authorization**.

## Memory Writes Should Be Controlled

This is especially important.

Do not give agents an unrestricted:

```text
remember(anything)
```

tool.

Instead:

```text
agent
  ↓
propose_memory()
  ↓
deterministic validation
  ↓
policy
  ↓
deduplicate / contradiction check
  ↓
store
```

Possible policy:

```yaml
memory:
  long_term:
    read: true

    write:
      mode: propose
      allowed_types:
        - preference
        - fact
        - decision
        - workflow_lesson

      require_approval:
        - sensitive
        - identity
        - security
```

This fits the approval/policy philosophy already present in the runtime.

## Runtime Integration

The runtime should know **how to use memory**, but not own the memory infrastructure.

Add:

```text
app/
└── integrations/
    └── memory/
        ├── __init__.py
        ├── client.py
        ├── schemas.py
        └── errors.py
```

Then expose explicit tools such as:

```text
memory_search
memory_propose
knowledge_search
```

Agent YAML can selectively enable them:

```yaml
memory:
  session:
    enabled: true

  long_term:
    enabled: true
    profile: henley

  knowledge:
    enabled: true
    collections:
      - henley-governing-documents
      - henley-board-minutes
```

This keeps **least privilege per agent**.

The NOTAM monitor, for example, may need no persistent conversational memory whatsoever.

A communications agent may need all three.

## Storage Recommendation

For the new service, I would start with:

```text
PostgreSQL
+
pgvector
+
optional S3/object references to source artifacts
```

rather than immediately adding another specialized database.

For your local MVP, PostgreSQL gives you:

- structured metadata;
- transactions;
- ACL fields;
- provenance;
- lifecycle records;
- full-text retrieval;
- vector retrieval;
- one backup boundary.

pgvector currently supports exact vector search plus HNSW and IVFFlat approximate indexes. 

I would preserve a `VectorStore` abstraction, however, so **Qdrant can later replace or supplement pgvector**. Qdrant has substantially richer dedicated vector-search capabilities, including payload filtering and hybrid/multi-stage retrieval, so it may become worthwhile as corpus size and retrieval complexity increase. 

So:

```text
V1        PostgreSQL + pgvector
Later     Qdrant if justified by scale/retrieval requirements
```

not:

```text
V1        PostgreSQL + Qdrant + Redis + another DB
```

Keep the first deployment understandable.

## End-to-End Architecture

```text
                       ┌──────────────────────────────┐
Documents ────────────►│ document-processing-platform │
                       │                              │
                       │ DocumentIR                   │
                       │ chunks                       │
                       │ metadata                     │
                       │ index-ready records          │
                       └──────────────┬───────────────┘
                                      │
                                      ▼
                       ┌──────────────────────────────┐
                       │ agent-memory-platform        │
                       │                              │
                       │ long-term memory             │
                       │ embeddings                   │
                       │ RAG indexes                  │
                       │ semantic search              │
                       │ hybrid retrieval             │
                       │ ACL / provenance             │
                       │ citations                    │
                       └──────────────┬───────────────┘
                                      │
                              narrow HTTP API
                                      │
                                      ▼
┌──────────────────────────────────────────────────────────┐
│ fastapi-openai-agents-runtime-framework                  │
│                                                          │
│ OpenAI Agents SDK                                        │
│ workflows / scheduler                                    │
│ session memory                                            │
│ memory_search tool ───────────────────────────────────────┤
│ knowledge_search tool                                    │
│ memory_propose tool                                      │
│ RuntimeStore: approvals/idempotency/audit only            │
└──────────────────────────┬───────────────────────────────┘
                           │
                           ▼
                  ┌────────────────────┐
                  │ Langfuse           │
                  │ traces/evaluation  │
                  └────────────────────┘
```

## Implementation Phases

### Phase A — Session Memory

Implement first because it is small and native to the Agents SDK.

- Add SDK `Session` support to `Runner.run()`.
- Add strict session configuration.
- Use separate persistent SQLite session DB.
- Add TTL/clear-session controls.
- Add isolation tests.
- Add approval-resume tests using the same session.
- Add Langfuse session correlation.

### Phase B — Memory Service Skeleton

Create:

```text
HomeAIassistant/agent-memory-platform
```

Implement:

- FastAPI.
- authentication;
- health/readiness;
- PostgreSQL;
- memory schema;
- project/user/agent scoping;
- deterministic write API;
- search API;
- Make/CI/security conventions matching the other platform repos.

### Phase C — Long-Term Memory

Add:

- `memory_search`;
- `memory_propose`;
- deduplication;
- supersession;
- expiration;
- confidence;
- provenance;
- deletion;
- memory audit trail.

**Do not initially implement automatic autonomous memory generation.**

Get explicit memory writes reliable first.

### Phase D — RAG

Connect `document-processing-platform` output to the memory platform.

Pipeline:

```text
document
→ DocumentIR
→ stable chunks
→ index-ready records
→ embedding
→ retrieval index
```

The processing repository already deliberately terminates at exactly this boundary. 

### Phase E — Retrieval Quality

Then add:

- lexical + vector hybrid search;
- metadata filtering;
- reranking;
- source deduplication;
- score thresholds;
- citation construction;
- retrieval evaluation sets.

### Phase F — Memory Intelligence

Only after the underlying controls are proven:

```text
episodic → semantic consolidation
memory importance scoring
contradiction detection
memory decay
memory summaries
automatic candidate extraction
```

## What I Would Not Do

I would **not**:

- add a `memory` table to the existing `RuntimeStore`;
- put Qdrant directly inside the runtime container;
- put RAG indexing inside agent execution;
- make Langfuse the memory database;
- make the document processor answer RAG queries;
- automatically save every conversation as long-term memory;
- automatically embed every Langfuse trace;
- let an LLM decide ACLs or memory scope;
- make every agent receive every memory collection.

Those approaches make the framework progressively harder to secure, reason about, test, and reuse.

# Final Recommendation

The repo separation should become:

| Repository | State | Responsibility |
|---|---|---|
| `fastapi-openai-agents-runtime-framework` | Mostly stateless | Agent execution, tools, workflows, scheduling, **session memory adapter** |
| `fastapi-openai-agents-langfuse` | Stateful | Observability and prompt/evaluation infrastructure |
| `document-processing-platform` | Stateful | Document ingestion, OCR, parsing, DocumentIR, chunks |
| **`agent-memory-platform`** | **Stateful** | **Long-term memory, embeddings, indexing, semantic retrieval, RAG** |

So the answer is **yes—create the fourth repo**.

But first I would add **Agents SDK session memory to the runtime framework itself**. That gives you proper multi-turn conversational memory immediately without prematurely building a large RAG system. The SDK explicitly describes sessions as its persistent working-context layer, separate from longer-term learned memory. 

Then build `agent-memory-platform` as the reusable stateful retrieval layer shared by **Henley, NOTAM workflows, future Gmail agents, document-backed agents, and other projects**, rather than making each agent invent its own vector database and memory implementation.

## Citation

OpenAI. “Sessions.” *OpenAI Agents SDK*, OpenAI, 2026. 

OpenAI. “Session.” *OpenAI Agents SDK API Reference*, OpenAI, 2026. 

OpenAI. “Agent Memory.” *OpenAI Agents SDK*, OpenAI, 2026. 

pgvector. “pgvector: Open-Source Vector Similarity Search for Postgres.” *GitHub*, 2026. 

Qdrant. “Hybrid and Multi-Stage Queries.” *Qdrant Documentation*, 2026. 


260808 - 14:08

