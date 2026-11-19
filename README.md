# SecureDocs

Secure enterprise document management and AI-powered knowledge retrieval using RAG.

**Current status: Authentication, private uploads, and asynchronous text processing.**
React + FastAPI + PostgreSQL (pgvector) + Redis/Celery, with organization-scoped documents, private local/S3 file storage, and TXT/PDF/DOCX extraction into searchable chunks.

## Stack

| Layer | Technology |
|---|---|
| Frontend | React 19, TypeScript, Vite, Tailwind CSS 4, Vitest |
| Backend | Python 3.12+, FastAPI, SQLAlchemy 2, Alembic, Pytest |
| Database | PostgreSQL 17 + pgvector |
| Queue | Redis + Celery worker |
| Storage | Private local volume for development; private AWS S3 for production |

## Prerequisites

Git, Python 3.12+, Node.js LTS, Docker Desktop.

## Run it locally

Use Docker Compose for the full stack. For manual local development, run PostgreSQL/Redis, the API, the Celery worker, and the frontend in separate terminals. Commands are for Windows PowerShell; macOS/Linux equivalents are noted.

### Run the full stack with Docker

From the repository root, build and start the API, frontend, PostgreSQL/pgvector, Redis, and document worker:

```powershell
docker compose up --build
```

In a second terminal, apply the database migration:

```powershell
docker compose exec backend alembic upgrade head
```

This applies the pgvector extension migration and creates the organization, user, document, document version, permission, processing-state, and document chunk tables. To create a migration after changing SQLAlchemy models, run `docker compose exec backend alembic revision --autogenerate -m "describe the schema change"`, review the generated file under `backend/alembic/versions/`, then apply it with `docker compose exec backend alembic upgrade head`. Do not edit migrations that have already been applied.

Open http://localhost:5173. The API docs are at http://localhost:8000/docs. Stop the stack with `Ctrl+C`; run `docker compose down` to stop and remove the containers.

For non-development deployments, set a unique `JWT_SECRET_KEY` of at least 48 characters and set `ENVIRONMENT` to `staging` or `production`. Generate a secret with `python -c "import secrets; print(secrets.token_urlsafe(48))"`. Access tokens expire after 60 minutes by default; the frontend keeps the token in tab-scoped `sessionStorage` and clears it when signing out.

### Authentication API

- `POST /api/v1/auth/register` accepts `email`, `password` (12–128 characters), `full_name`, and `organization_name`. It creates the user, organization, and owner membership, then returns a bearer token and user profile.
- `POST /api/v1/auth/login` accepts `email` and `password` and returns a bearer token and user profile.
- `GET /api/v1/auth/me` returns the current user and requires `Authorization: Bearer <access_token>`.

In Swagger at http://localhost:8000/docs, register or log in first, copy `access_token`, choose **Authorize**, and paste the token value to try `/auth/me` (Swagger adds the `Bearer` prefix).

Frontend routes: `/` redirects to login (or the dashboard for an existing session), `/login` and `/register` are guest pages, `/dashboard` and `/documents` require a valid session, and `/status` remains available for service diagnostics.

### Documents and file uploads

All document routes require a valid bearer token and an organization membership. For this first organization-aware workflow, documents are created in the user’s registration organization; list, detail, update, and delete queries are scoped to that organization. Documents created by another organization return `404`. Owners and administrators can edit or delete any document in their organization; members can manage their own documents, and viewers have read-only access. A document metadata update creates a new `document_versions` snapshot.

- `POST /api/v1/documents/upload` accepts multipart `file` and optional `description`. PDF, UTF-8 plain text, and DOCX are supported, up to 10 MiB by default. The API validates the declared MIME type, extension, size, and file content before storing.
- `GET /api/v1/documents?offset=0&limit=100` lists organization documents.
- `GET /api/v1/documents/{id}` returns metadata and version history.
- `PATCH /api/v1/documents/{id}` updates metadata and records a new version.
- `POST /api/v1/documents/{id}/retry` requeues a failed or not-yet-started file for processing.
- `GET /api/v1/documents/{id}/download` streams the private file after checking the user's organization membership.
- `DELETE /api/v1/documents/{id}` deletes the private object and its record/version/permission rows.

The upload request stores the file and metadata, queues a Celery task, and returns without doing extraction in the request. The worker extracts TXT, PDF, or DOCX text, normalizes it, splits it into overlapping chunks, generates embeddings in batches, and marks the document `ready` only after every chunk has a vector. Text chunks are committed before embedding so they survive provider failures; retry resumes embedding from saved chunks. Embeddings use OpenRouter's `qwen/qwen3-embedding-8b` model, with 4096-dimensional vectors. OpenRouter's compatible embeddings endpoint is `https://openrouter.ai/api/v1/embeddings`; the provider validates the returned vector size. For Docker Compose, put `OPENROUTER_API_KEY` in the ignored root `.env`; for a manually run backend, put it in ignored `backend/.env`. Use `.env.example` files as templates only. The timeout is 20 seconds, transient worker failures retry up to three times, and batches contain at most 64 chunks. The default per-document and query budgets are 100,000 and 2,048 UTF-8 bytes. Redis enforces a 25-million monthly usage reservation ceiling by default (`EMBEDDING_MONTHLY_TOKEN_LIMIT`); reservation counts use a conservative UTF-8-byte upper bound. OpenRouter lists a 40,960-token model input limit and current pricing of $0.01 per million tokens; provider pricing can vary, so the application enforces a usage-token cap rather than an assumed dollar budget. Search is exact cosine search (no approximate index yet).

- `POST /api/v1/search` accepts `{ "query": "...", "top_k": 8 }` and returns only ready chunks belonging to the authenticated user's organizations. The membership filter is part of the vector SQL query.
- `/search` is the authenticated frontend search page. Documents must be fully embedded to appear in results.
- A starter retrieval evaluation set is in `docs/search-evaluation.json`. Replace its expected-document/section placeholders with known passages from a small uploaded corpus. For each query record whether the expected document and chunk appear in the top-k results, latency, and whether a different organization’s content ever appears; include empty and ambiguous queries before relying on retrieval quality.

Apply migrations with `docker compose exec backend alembic upgrade head`. Provider/dimension changes reset old vectors and mark processed documents failed so they can be retried. OCR for scanned PDFs remains out of scope; scanned PDFs with no selectable text receive an OCR-required error.

The storage key and filesystem path are never returned in API responses. Local uploads are stored in the Docker `document_uploads` volume at `/app/private_uploads`, mounted by both the API and worker outside the served frontend and API static paths. Celery uses Redis database 1 by default; the app's Redis services use database 0.

For production, set `STORAGE_BACKEND=s3`, `S3_BUCKET` to a private bucket, and optionally `S3_REGION`, `S3_PREFIX`, and `S3_SERVER_SIDE_ENCRYPTION` (`AES256` or `aws:kms`). Give the backend IAM role only the required object access to that bucket/prefix; the adapter does not make objects public and applies server-side encryption. Configure AWS credentials using the standard SDK provider chain. Set `UPLOAD_MAX_BYTES` to the desired limit in bytes; the frontend reads the same value through Compose. S3 downloads are proxied through the authenticated API rather than exposing bucket URLs.

### 1. Infrastructure (Postgres + pgvector, Redis)

```powershell
docker compose up -d
docker ps
```

You should see `securedocs-postgres` and `securedocs-redis`, both `healthy`, along with the API, frontend, and worker containers.

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

### 3. Document worker (manual local development)

After applying migrations, run the worker from the `backend` directory. On Windows use Celery's `solo` pool; Linux/macOS can use its default prefork pool.

```powershell
cd backend
celery -A app.workers.celery_app:celery_app worker --loglevel=INFO --pool=solo
```

### 4. Frontend

```powershell
cd frontend
npm install
npm run dev
```

Open http://localhost:5173. The status page checks API dependencies; the Celery worker is visible with `docker compose ps` or `docker compose logs worker`.

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
  api/v1/      health, auth, organization-scoped documents
  services/    extraction, normalization, chunking, business logic
  schemas/     Pydantic request/response models
  models/      SQLAlchemy models (Phase 2+)
  rag/         RAG pipeline (later phases)
  workers/     Celery app and document processing tasks
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
