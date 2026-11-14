# SecureDocs

Secure enterprise document management and AI-powered knowledge retrieval using RAG.

**Current status: Phase 1 - local development foundation.**
React + FastAPI + PostgreSQL (pgvector) + Redis, with a status page that proves every piece is connected.

## Stack

| Layer | Technology |
|---|---|
| Frontend | React 19, TypeScript, Vite, Tailwind CSS 4, Vitest |
| Backend | Python 3.12+, FastAPI, SQLAlchemy 2, Alembic, Pytest |
| Database | PostgreSQL 17 + pgvector |
| Queue (later) | Redis + Celery |
| Storage (later) | AWS S3 |

## Prerequisites

Git, Python 3.12+, Node.js LTS, Docker Desktop.

## Run it locally

Use three terminals. Commands are for Windows PowerShell; macOS/Linux equivalents are noted.

### 1. Infrastructure (Postgres + pgvector, Redis)

```powershell
docker compose up -d
docker ps
```

You should see `securedocs-postgres` and `securedocs-redis`, both `healthy`.

### 2. Backend

```powershell
cd backend
python -m venv venv
venv\Scripts\activate          # macOS/Linux: source venv/bin/activate
pip install -r requirements-dev.txt
copy .env.example .env         # macOS/Linux: cp .env.example .env
alembic upgrade head           # enables the pgvector extension
uvicorn app.main:app --reload
```

- API docs: http://localhost:8000/docs
- Liveness: http://localhost:8000/api/v1/health
- Dependencies: http://localhost:8000/api/v1/health/services

### 3. Frontend

```powershell
cd frontend
npm install
npm run dev
```

Open http://localhost:5173. All three services should show **Connected**.

## Tests

```powershell
cd backend;  pytest
cd frontend; npm test
```

## Phase 1 done when

- [ ] `docker ps` shows Postgres and Redis healthy
- [ ] `alembic upgrade head` succeeds
- [ ] `/docs` loads
- [ ] The status page shows PostgreSQL, pgvector and Redis as Connected
- [ ] `pytest` and `npm test` pass

## Project layout

```
backend/app/
  core/        config, database, redis
  api/v1/      routers (health now; auth, documents, search, chat later)
  services/    business logic
  schemas/     Pydantic request/response models
  models/      SQLAlchemy models (Phase 2+)
  rag/         RAG pipeline (later phases)
  workers/     Celery tasks (later phases)
frontend/src/
  api/ hooks/ components/ pages/ types/
infrastructure/  docker, nginx, aws (later)
docs/            architecture notes
```

## Roadmap

1. Foundation (this phase)
2. Authentication (JWT, roles, organizations)
3. Document management (upload, list, download)
4. AWS S3 storage
5. PDF extraction and chunking
6. Embeddings and pgvector storage
7. Semantic search
8. RAG answers with citations
9. Background workers (Celery + Redis)
10. Security (RBAC, document permissions, audit logs, signed URLs)
11. Advanced RAG (hybrid search, reranking, comparison)
12. AWS deployment

## Notes

- PostgreSQL 17 is used for the local image. The pgvector image for 18 mounts its data directory at a different path, so 17 keeps the volume config simple. Move to 18 when you deploy if you want it.
- Secrets live in `backend/.env`, which is git-ignored. Only `.env.example` is committed.
