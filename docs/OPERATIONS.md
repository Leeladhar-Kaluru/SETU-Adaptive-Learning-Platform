# SETU Operations Guide

Last verified: 2026-10-29 (Task 17 final verification)

This guide records the commands that were actually run in this repository. It
does not contain secret values. Environment names are listed so operators know
what must exist; the values belong in `backend/.env` or the process environment.

## 1. Prerequisites

| Requirement | Verified local version / state |
|---|---|
| Windows PowerShell | Used for every command in this guide |
| Python | `backend/.venv` exists; run backend commands with `backend\.venv\Scripts\python.exe` |
| Node.js + npm | Frontend build and Playwright ran successfully |
| Docker Desktop | Test database container `backend-postgres-test-1` is healthy at `127.0.0.1:55432` |
| Tesseract data | `backend/tessdata/eng.traineddata` is present; OCR is used only for scanned or corrupted pages |
| LM Studio | Must run at `http://127.0.0.1:1234/v1` with `google/gemma-4-e4b` and `text-embedding-nomic-embed-text-v1.5` |
| PostgreSQL + pgvector | Production Supabase and the disposable test database both provide pgvector |

The application is a React 19 + Vite + TypeScript frontend (CSS Modules, no
Tailwind) and a FastAPI backend on Supabase PostgreSQL/Auth/Storage.

## 2. Environment names

Create `backend/.env` with these names. Values are intentionally omitted.

```dotenv
APP_ENV=local
LOG_LEVEL=INFO
FRONTEND_ORIGINS=http://localhost:5173,http://127.0.0.1:5173
DATABASE_URL=
SUPABASE_URL=
SUPABASE_PUBLISHABLE_KEY=
SUPABASE_SECRET_KEY=
ENABLE_REMOTE_AI=true
LLM_BASE_URL=http://127.0.0.1:1234/v1
LLM_MODEL=google/gemma-4-e4b
EMBEDDING_MODEL=text-embedding-nomic-embed-text-v1.5
```

- `DATABASE_URL` is a direct PostgreSQL connection string.
- `SUPABASE_SECRET_KEY` is server-only. Never expose it to Vite, the browser,
  logs, screenshots, or committed files.
- `SETU_TEST_AUTH` enables test-only header authentication and must remain
  `false` outside the test process.
- The frontend uses the API through Vite's `/api` proxy. It does not read
  service-role credentials.

## 3. Install

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt

cd ..\frontend
npm install
```

## 4. Databases and migrations

### Production / configured database

Alembic resolves the database from `settings.DATABASE_URL`, which reads
`backend/.env` or the process environment. Run Alembic from the repository root
so `script_location = backend/alembic` resolves correctly.

```powershell
$env:DATABASE_URL="<connection string>"
.\backend\.venv\Scripts\alembic.exe -c backend\alembic.ini upgrade head
.\backend\.venv\Scripts\alembic.exe -c backend\alembic.ini current
.\backend\.venv\Scripts\alembic.exe -c backend\alembic.ini heads
```

Migration `007` is the current head. The observed final check on the disposable
test database was:

```text
007 (head)
007 (head)
```

The first line is `current`; the second is `heads`.

### Disposable test database

```powershell
docker compose -f backend/docker-compose.test.yml up -d
```

This starts `pgvector/pgvector:pg16` on `127.0.0.1:55432` with database
`setu_test`, user `setu`, and the disposable test password from the compose
file. The data directory is `tmpfs`, so stopping the container discards it.

Apply migrations to the test database:

```powershell
$env:DATABASE_URL="postgresql://setu:setu_test@127.0.0.1:55432/setu_test"
.\backend\.venv\Scripts\alembic.exe -c backend\alembic.ini upgrade head
```

## 5. Run SETU locally

Use three processes.

### Backend API

```powershell
cd backend
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

### Durable background worker

```powershell
cd backend
.\.venv\Scripts\python.exe -m app.worker
```

The worker claims stored documents and queued lesson-generation jobs with
`FOR UPDATE SKIP LOCKED` leases. Expired leases are returned to the queue, and
attempts are bounded. Run at least one worker; without it, uploads remain
`stored` and lessons remain `queued`.

### Frontend

```powershell
cd frontend
npm run dev
```

Open `http://localhost:5173`. The preview server used by Playwright is started
by `playwright.config.ts` through `npm run preview` on port `5173`.

## 6. LM Studio and the 768-dimension contract

1. Start LM Studio's local server at `http://127.0.0.1:1234/v1`.
2. Load `google/gemma-4-e4b` for chat and
   `text-embedding-nomic-embed-text-v1.5` for embeddings.
3. Probe the application health endpoint while the backend is running:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/v1/health | ConvertTo-Json -Depth 6
```

A healthy provider reports `chat_ready: true`, `embed_ready: true`, and
`probed_dimension: 768`. The backend rejects any embedding whose length is not
`EMBEDDING_DIMENSION` (768) instead of writing a corrupt vector.

Direct provider probe:

```powershell
$body = @{
  model = "text-embedding-nomic-embed-text-v1.5"
  input = "dimension probe"
} | ConvertTo-Json
$response = Invoke-RestMethod -Method Post `
  -Uri http://127.0.0.1:1234/v1/embeddings `
  -ContentType "application/json" -Body $body
$response.data[0].embedding.Count
```

Expected output: `768`.

## 7. Tests and verification

### Backend

The suite uses the disposable test database. Integration tests that require a
live LLM are skipped unless `SETU_TEST_LLM_URL` is set.

```powershell
cd backend
$env:SETU_TEST_DATABASE_URL="postgresql://setu:setu_test@127.0.0.1:55432/setu_test"
.\.venv\Scripts\python.exe -m pytest -q
```

Final observed result on 2026-10-29: `104 passed, 6 skipped, 2 warnings`.

### Frontend build

```powershell
cd frontend
npm run build
```

The build runs `tsc -b` before Vite. The only warning is the >500 kB
application chunk; it is not a build failure.

### Browser acceptance (Chromium)

Build first, because Playwright serves the production preview.

```powershell
cd frontend
npx playwright test --project=chromium
```

Final observed result on 2026-10-29: `17 passed`.

The `ECONNREFUSED` proxy lines printed by the preview server are expected:
individual specs mock API routes, and the preview proxy reports the requests
that the test did not route to a mock.

## 8. Data lifecycle

1. **Upload** — `POST /api/v1/documents/upload` validates size (50 MB), extension,
   and file signature, writes the private object to the `setu-documents`
   bucket, and creates a `documents` row with status `stored`.
2. **Extraction** — the worker claims the document (`extracting`), extracts each
   page, applies OCR only to scanned or corrupted pages, and records per-page
   quality. Unreadable pages are flagged; placeholder text is never substituted.
3. **Indexing** — usable text is chunked, embedded at 768 dimensions, and stored
   with full-text search data. Failing embeddings stop the document instead of
   storing invalid vectors.
4. **Review** — a document with usable text becomes `ready_for_review`. The
   student reviews the detected chapters and page ranges before building a path.
5. **Path and lessons** — path creation writes `learning_paths`, `path_lessons`,
   and idempotent `generation_jobs`. The first lesson has priority; later
   lessons wait in the durable queue.
6. **Lesson publication** — the worker generates and validates a typed lesson
   package, stores a `lesson_versions` row, and marks the lesson `ready` only
   when its source references, questions, and visual specs pass validation.
7. **Learning evidence** — practice and checkpoint attempts are graded on the
   server and recorded as evidence. Teacher dashboards read only authorized
   classroom records.
8. **Doubts** — online doubts are answered immediately through the retrieval and
   model path. A genuine browser-offline event queues the doubt in IndexedDB;
   reconnect sync is idempotent by client-generated ID. Provider failures are
   surfaced as retryable states, not silently queued.
9. **Offline lessons** — downloaded lesson packages live in IndexedDB. Saving
   failures are shown to the student instead of disappearing.

## 9. Scoped cleanup

The scoped cleanup tool is read-only by default:

```powershell
.\backend\.venv\Scripts\python.exe backend\scripts\cleanup_demo_data.py --inventory
```

Applying it requires the exact confirmation token, explicit demo profile IDs,
and the preserved real profile ID:

```powershell
.\backend\.venv\Scripts\python.exe backend\scripts\cleanup_demo_data.py --apply `
  --confirm APPLY-CLEANUP `
  --delete-user-id <demo-uuid> [--delete-user-id <demo-uuid> ...] `
  --preserve-user-id <real-profile-uuid>
```

The test-domain heuristic is not authorization. A human must name the records.
The last scoped cleanup (Task 2) deleted eight `example.com` profiles and the
26 seeded resource/rights rows while preserving the real Gmail profile.

## 10. Emergency application reset

`backend/scripts/reset_supabase_app_data.py` is a last resort. Without
`--apply` it only prints a read-only inventory:

```powershell
.\backend\.venv\Scripts\python.exe backend\scripts\reset_supabase_app_data.py
```

A destructive run requires all three gates:

```powershell
.\backend\.venv\Scripts\python.exe backend\scripts\reset_supabase_app_data.py --apply `
  --confirm DROP-ALL-APPLICATION-TABLES `
  --backup <path-to-non-empty-database-dump> `
  --allow-production SETU-PRODUCTION-RESET
```

What it does:

- Drops application tables in `public` with `CASCADE`.
- Deletes objects in the `setu-documents` storage bucket.
- Preserves Supabase-managed schemas (`auth`, `storage`, `vault`, `realtime`,
  `extensions`, and related managed schemas).
- Preserves `auth.users`; it does not delete accounts.
- Writes a timestamped `context/RESET_REPORT.<UTC>.md` and updates
  `context/RESET_REPORT.md` to index the latest report.
- Never prints the database URL, password, or service key.

**No broad reset was run in Tasks 1–17.** The production database was only
inspected read-only, and the approved Task 2 cleanup was scoped by explicit
profile IDs.

## 11. Backups

Create a local backup before any destructive database operation:

```powershell
.\backend\.venv\Scripts\python.exe backend\scripts\backup_supabase.py
```

The script reads `backend/.env` and writes a timestamped SQL backup plus a JSON
manifest under `backend/backups/`. The manifest records schemas, tables, storage
metadata, extension versions, and redacted auth-user counts. Verify the backup
file is non-empty before passing it to the reset script.

For an operator-managed dump, `pg_dump` with the direct connection string is
also acceptable. Keep dumps out of version control.

## 12. Troubleshooting

| Symptom | Cause and action |
|---|---|
| Upload stays `stored` | No worker is running. Start `python -m app.worker`. |
| Lesson stays `queued` | No worker, or the worker cannot reach the model provider. Check the worker log and `/api/v1/health`. |
| Health is `degraded` | Inspect `components.database`, `components.storage`, and `components.ai_provider`. A provider dimension other than 768 is a hard failure. |
| `ECONNREFUSED` in Playwright output | Expected preview-proxy noise for mocked API calls. A real failed assertion is separate. |
| Integration tests skip | Set `SETU_TEST_LLM_URL` to a live compatible endpoint; the six skipped tests are model-dependent. |
| `fitz` deprecation warning | PyMuPDF emits it on import. It does not change extraction behaviour. |
| Vite chunk-size warning | The application bundle is slightly over 500 kB. It is a warning, not a failure. |
| CORS error in the browser | Add the exact frontend origin to `FRONTEND_ORIGINS` and restart the API. |
| Table count changes after a test run | The backend tests use the disposable `setu_test` database, not production. Confirm `SETU_TEST_DATABASE_URL` before interpreting counts. |

## 13. Acceptance evidence

- `STATUS_REPORT.md` — session changes, exact commands, observed results,
  blockers, and next actions.
- `context/ACCEPTANCE_MATRIX.md` — pass/fail/blocked/not-run acceptance status
  with observed evidence only.
- `docs/UI_ACTION_AUDIT.md` — every visible control and how it was verified.
- `context/SUPABASE_CLEANUP_MANIFEST.md` — final production inventory and the
  scoped cleanup record.
- `context/RESET_REPORT.md` — index of timestamped emergency reset reports.
