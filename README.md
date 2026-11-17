# SecureDocs

Secure enterprise document management and AI-powered knowledge retrieval using RAG.

**Current status: Authentication and document metadata foundation.**
React + FastAPI + PostgreSQL (pgvector) + Redis, with account registration, organization-scoped document metadata, bearer-token authentication, protected workspace routes, and service diagnostics.

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

### Run the full stack with Docker

From the repository root, build and start the API, frontend, PostgreSQL/pgvector, and Redis:

```powershell
docker compose up --build
```

In a second terminal, apply the database migration:

```powershell
docker compose exec backend alembic upgrade head
```

This applies the pgvector extension migration and creates the `organizations`, `users`, `organization_members`, `documents`, `document_versions`, and `document_permissions` tables. To create a migration after changing SQLAlchemy models, run `docker compose exec backend alembic revision --autogenerate -m "describe the schema change"`, review the generated file under `backend/alembic/versions/`, then apply it with `docker compose exec backend alembic upgrade head`. Do not edit migrations that have already been applied.

Open http://localhost:5173. The API docs are at http://localhost:8000/docs. Stop the stack with `Ctrl+C`; run `docker compose down` to stop and remove the containers.

For non-development deployments, set a unique `JWT_SECRET_KEY` of at least 48 characters and set `ENVIRONMENT` to `staging` or `production`. Generate a secret with `python -c "import secrets; print(secrets.token_urlsafe(48))"`. Access tokens expire after 60 minutes by default; the frontend keeps the token in tab-scoped `sessionStorage` and clears it when signing out.

### Authentication API

- `POST /api/v1/auth/register` accepts `email`, `password` (12–128 characters), `full_name`, and `organization_name`. It creates the user, organization, and owner membership, then returns a bearer token and user profile.
- `POST /api/v1/auth/login` accepts `email` and `password` and returns a bearer token and user profile.
- `GET /api/v1/auth/me` returns the current user and requires `Authorization: Bearer <access_token>`.

In Swagger at http://localhost:8000/docs, register or log in first, copy `access_token`, choose **Authorize**, and paste the token value to try `/auth/me` (Swagger adds the `Bearer` prefix).

Frontend routes: `/` redirects to login (or the dashboard for an existing session), `/login` and `/register` are guest pages, `/dashboard` and `/documents` require a valid session, and `/status` remains available for service diagnostics.

### Document metadata API

All document routes require a valid bearer token and an organization membership. For this first organization-aware workflow, documents are created in the user’s registration organization; list, detail, update, and delete queries are scoped to that organization. Documents created by another organization return `404`. Owners and administrators can edit or delete any document in their organization; members can manage their own documents, and viewers have read-only access. A document metadata update creates a new `document_versions` snapshot.

- `POST /api/v1/documents` accepts `name`, optional `description`, `mime_type`, and `file_size` (bytes); no file is stored yet.
- `GET /api/v1/documents?offset=0&limit=100` lists organization documents.
- `GET /api/v1/documents/{id}` returns metadata and version history.
- `PATCH /api/v1/documents/{id}` updates metadata and records a new version.
- `DELETE /api/v1/documents/{id}` deletes the record and its version/permission rows.

The Documents page supports creating metadata records and deleting them. Real upload, private local storage, S3, and download URLs are not enabled yet.

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
