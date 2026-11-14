# Architecture

## Five systems

1. Identity: users, roles, organizations, JWT
2. Document management: upload, download, metadata, versioning
3. Document processing: extraction, OCR, cleaning, chunking
4. RAG: embeddings, retrieval, generation, citations
5. Security and audit: RBAC, document permissions, audit logs, signed URLs

## Request flow (target)

```
React -> Nginx -> FastAPI -> PostgreSQL + pgvector
                          -> Redis -> Celery worker -> RAG pipeline
                          -> AWS S3
```

## Principles

- Authorize first, then search: vector retrieval is always scoped to documents the user may access.
- The backend attaches citations from retrieved chunks; the LLM never invents source IDs.
- Embedding and LLM providers sit behind `backend/app/rag/` interfaces so they can be swapped.
- Files live in S3 (never public); PostgreSQL stores metadata, permissions, chunks and vectors.
