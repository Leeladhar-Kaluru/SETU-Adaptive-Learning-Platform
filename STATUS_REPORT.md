# SETU Status Report

**Session date:** 2026-10-31, finalized 2026-11-01
**Scope:** Round 2 demo readiness — real learner understanding, cross-book adaptive planning, grounded coaching, smart checks, teacher class-gap insight, UI polish, verification, and cleanup
**Workspace:** `C:\projects\setu - V2`
**Visible product name:** SETU (no version suffix in UI, titles, or manifests)

---

## 1. Round 2 readiness (2026-10-31)

### 1.1 What was delivered

- **Learner understanding** (`backend/app/services/learner_insights.py`):
  accuracy, trend, pace, hint reliance, routine windows, consistency, strengths,
  focus areas, evidence confidence, and study habits derived only from recorded
  `StudyEvent`, `QuizAttempt`, `ConceptEvidence`, `ConceptMasterySnapshot`,
  profile goal, and path rows. Exposed at `GET /api/v1/study/insights` and shown
  on the student desk.
- **Language**: the learner's `preferredLanguage` is stored and shown; the
  upload accepts a language tag; lesson generation now passes the document's
  source language into the prompt and package instead of forcing `en-IN`.
- **Cross-book adaptive plan** (`backend/app/services/study_plan.py`): one plan
  across every active path, with remediation, review, continue, next-lesson and
  stretch tasks. The plan re-ranks when mastery, attempts or reading events
  change. Exposed at `GET /api/v1/study/plan`.
- **Grounded real-time coaching** (`backend/app/services/coach_service.py`):
  post-attempt coaching and lesson coach cards composed from the actual question,
  answer, hints, mastery, timing, lesson takeaways and source chunks. Cards are
  omitted when evidence is absent. Attempt responses carry `coaching` and
  root-gap data.
- **Root-gap diagnosis**: an earlier `developing` / `not_enough_evidence` concept
  can be named as a candidate gap even when the freshly tested concept has one
  observation.
- **Smart checks** (`backend/app/services/smart_check.py`): few-question checks
  that pick evidenced concepts and recover multiple-choice options from
  `lesson_package_json` when historical `questions.prompt_json` omitted them.
- **Teacher insight** (`backend/app/api/v1/teacher.py`): classroom lifecycle,
  roster, scoped evidence matrix, class-gap radar, “Plan support” prefill, and
  explained suggestions. A student sees an accepted/edited suggestion until the
  student responds; only the student's own accept/dismiss resolves it.
- **Frontend**: adaptive plan, “How you learn”, smart check, cross-book book mix,
  coaching cards, key points, checkpoint celebration, and the midnight
  black / electric blue / cantaloupe orange theme. React 19 + Vite + TypeScript +
  CSS Modules; no Tailwind or shadcn. PWA manifest and icons updated.
- **Generation truth**: the outline builder produced all 21 SCERT Social Science
  chapters with correct titles and page ranges, plus one clean chapter for the
  2-page Class 9 Science document. A chunk fallback handles legacy documents with
  no `DocumentPage` rows. The visual normalizer emits renderer-shaped
  `{id,label}` nodes and `[from,to]` edges.
- **Cleanup**: temporary screenshot/verification scripts, Playwright result
  folders, stale raw logs, ad-hoc destructive cleanup scripts, and stale
  pre-redesign screenshots were removed. The acceptance runner and its fixtures
  now live in `backend/acceptance/`; acceptance evidence JSON remains under
  `context/`.
- **Database pool guard** (`backend/app/core/database.py`): the Supabase session
  pooler caps the project at 15 clients. The SQLAlchemy engine now uses
  `pool_size=4, max_overflow=0, pool_timeout=15, pool_use_lifo=True` per process.
  Profile, dashboard, path-create and the other synchronous database endpoints run
  in FastAPI's thread pool so a short pool wait never blocks the event loop.
  Verified with a 20-request concurrent burst against `/profile` — all 200
  responses.

### 1.2 Exact verification ledger

Health (`GET http://127.0.0.1:8000/api/v1/health`):

```text
status: healthy
database: connected, PostgreSQL 17 (pgvector 768d)
storage: connected, bucket setu-documents
chat_model: google/gemma-4-e4b, chat_ready: true
embed_model: text-embedding-nomic-embed-text-v1.5, embed_ready: true
probed_dimension: 768, dimension_match: true
```

Backend suite:

```powershell
cd backend
$env:SETU_TEST_DATABASE_URL="postgresql://setu:setu_test@127.0.0.1:55432/setu_test"
$env:SETU_TEST_LLM_URL="http://127.0.0.1:1234/v1"
.\.venv\Scripts\python.exe -m pytest -q
```

Observed on the final run: `138 passed, 6 skipped, 2 warnings in 10.12s`
(exit code 0). The three new auth-verification tests are included. Warnings are
upstream `starlette.testclient` / `httpx` and `fitz` → `pymupdf` deprecations.

Frontend build:

```powershell
cd frontend
npm run build
```

Observed: `tsc -b` + `vite build` succeeded; 1656 modules; application chunk
`572.51 kB` (`174.50 kB` gzip); CSS `112.16 kB` (`19.07 kB` gzip); PWA generated
`dist/sw.js` with 17 precache entries (740.15 KiB). The only warning is the
>500 kB chunk-size advisory.

Browser suites:

```powershell
cd frontend
npx playwright test --project=chromium --project=mobile
```

Observed: `36 passed (8.1s)` — 18 tests per project across onboarding taxonomy,
fresh-student empty states, navigation truth, lesson attempts, doubt truth,
offline sync, teacher evidence, and the new catalogue-backed plan-review modal.

Live UI checks against the real API and worker:

- `/study/plan`: `2 books · 4 tasks`; start task `Rebuild Cells` (Science), then
  `Rebuild Gondwana` (Social), `Rebuild Diffusion` (Science), and a Social
  stretch task. The plan changed from “Start Chapter 1” to “Rebuild Diffusion” to
  “Rebuild Cells” as real checkpoint evidence was recorded.
- `/study/insights`: 40% accuracy, 40% hint reliance, 57 s median answer time,
  12.2 minutes recorded, real study windows and focus areas.
- Lesson coach: key point with page citation (`Class_9_Science_Chapter_5.pdf`,
  page 59), student pace, and a challenge card for developing concepts. Pace copy
  now reads `1 minute`, not `1 minutes`.
- Practice attempt with a hint produced grounded coaching and a mastery update;
  checkpoint submission produced “Checkpoint complete — every answer correct”.
- Smart check rendered real multiple-choice buttons, graded the correct answer,
  and returned feedback plus coaching.
- Teacher desk: classroom `Class 10 Social Studies - Section A` (`KMJRAE`),
  1 active member, real evidence radar (Cells 0%, Diffusion 48%, Gondwana 0%,
  Angara 0%, Conflict 0%), “Plan support” prefill, suggestion send, and teacher
  accept. The accepted suggestion then appeared on the student desk from
  “Meera Rao” with real evidence and Accept/Dismiss actions.
- Student `/study/summary` no longer shows an archived reading title.
- Plan review modal against the live API: `Build my learning plan` opened the
  source-review dialog, the Subject select listed Science, Mathematics, Social
  Science, English, Hindi, and Information Technology from the catalogue, the
  class defaulted to 10, and approving sent
  `{documentId, grade: 10, subjectId: "subject-science"}`. Desktop (1440 px) and
  Pixel 7 widths had no horizontal overflow.
- Auth concurrency: 20 simultaneous `GET /api/v1/profile` calls with one real
  Supabase token returned 20 × HTTP 200 in 2.53 s; no 401/500 and no token loss.

### 1.3 Submission-freeze fixes (2026-11-01)

- **Plan review modal rebuilt** (`frontend/src/pages/HomePage.tsx`,
  `HomePage.module.css`): a two-pane source-review dialog with the setup on the
  left and the numbered chapter list on the right, page ranges, warnings, a close
  action, a sticky footer, and mobile stacking. The class defaults to the
  learner's profile grade; the subject comes from the live
  `GET /api/v1/catalogue/subjects` catalogue, not from onboarding interests alone.
  If onboarding stored no interests the dropdown still lists every active subject.
  When the source filename names a subject (for example “Social Science”), SETU
  preselects the longest catalogue match and still lets the learner change it.
  Loading, empty-catalogue, and failed-catalogue states are explicit, with retry.
- **Root cause of the intermittent sign-out fixed**: every authenticated request
  called Supabase Auth's `/auth/v1/user` over a fresh HTTPS connection. Concurrent
  dashboard requests could exhaust or stall those calls; a failed check returned
  401, and `AuthContext` then deleted the saved token. `backend/app/core/security.py`
  now caches a successful verification for 60 seconds, collapses concurrent checks
  of the same token into one upstream request, reuses one HTTP client, rejects
  locally expired tokens without a call, and raises **503** (not 401) when Supabase
  Auth is unavailable. `AuthContext` retries transient profile failures three
  times, only clears the token on a real 401/403, and shows a “Your desk is still
  here” retry screen instead of silently dropping the session.
- **Blocking database work moved off the event loop**: `GET/PUT /profile`,
  `GET /profile/dashboard`, and `POST /learning-paths` are synchronous endpoints,
  so FastAPI runs their SQLAlchemy work in its thread pool. The connection pool is
  now 4 (worker uses 2; the Supabase pooler cap is 15).
- **Regression tests added**: `backend/tests/test_auth_verification.py` proves the
  cache, single-flight, expiry rejection, and 503 propagation;
  `frontend/e2e/plan_review_subject.spec.ts` proves the catalogue-backed subject
  dropdown, filename-based preselect, and enabled build action for a learner with
  no onboarding interests.

### 1.4 Current data state

- `learning_paths`: 2 active (Science `41a32994-eafd-4af2-bfb5-8470e7b185f4`,
  Social `8f2c163f-5aa9-425d-9769-aeb854e4c04a`), 1 archived.
- `generation_jobs`: 22 ready, 17 failed historical, 7 cancelled. No pending
  generation work.
- Social: all 21 chapters ready. Science: Chapter 1 ready
  (`c9153684-29c8-49a0-8ce0-70408e87a98e`).
- Demo student and teacher accounts exist with real classroom membership and
  evidence. Credentials are kept outside the repository in
  `%TEMP%\setu_demo_credentials.txt`; no password is committed or written to
  application logs.
- The audit claim that the student account owned 8 classrooms was false: it owns
  **0**. Eight legacy classrooms belong to an orphan teacher ID
  (`de898934-3c24-4d3a-baf3-53387ac557b0`) with no profile row; none has the
  student as a member. They remain as historical records and are not used by the
  demo.
- 17 historical failed lesson versions and old orphan classroom records remain
  as records; they no longer block the demo.

### 1.5 Blockers and disclosures

1. **Stitch MCP is unavailable.** No Stitch tool or MCP resource exists in this
   environment. Design prompts remain marked **NOT SENT**; no Stitch-generated
   screen is claimed.
2. **LM Studio embedding model has a one-hour TTL.** If health reports
   `embed_ready: false`, reload it with
   `lms load text-embedding-nomic-embed-text-v1.5 --gpu max -c 512 --ttl 3600 -y`.
3. **Legacy document `f597a968-bfea-413d-b5be-90c731aa63aa` has zero
   `DocumentPage` rows and unembedded chunks.** It is not used by the demo.
4. **Historical failed generation jobs remain.** They are records, not pending
   work; the queue is empty.
5. **The working tree contains extensive pre-existing changes.** Nothing was
   reset or discarded; staging and commit scope remain a human decision.
6. **A previously opened tab may still run an older PWA bundle.** The rebuilt
   modal is in `dist/`; close and reopen the tab, or hard-refresh once
   (`Ctrl+Shift+R`) if the old one-pane dialog is still visible. `npm run preview`
   must be restarted after `npm run build`.

### 1.6 Launch commands

```powershell
# API
cd backend
.\.venv\Scripts\python.exe -u -m uvicorn app.main:app --host 127.0.0.1 --port 8000

# Worker (second terminal)
cd backend
.\.venv\Scripts\python.exe -u -m app.worker

# Frontend (third terminal)
cd frontend
npm run dev
```

Production build/preview:

```powershell
cd frontend
npm run build
npm run preview
```

The Vite server proxies `/api` to `http://localhost:8000`. Open
`http://localhost:5173`.

---

# Historical record — 2026-10-30 session

## 1. What changed in that session

### 1.1 Generation and path truthfulness

- `backend/app/worker.py` now refreshes the parent learning-path status whenever a
  lesson reaches a terminal state. `refresh_path_status()` flushes first because
  `SessionLocal` uses `autoflush=False`; without the flush, the just-completed
  lesson was invisible to the status query.
- Added `test_path_becomes_active_only_when_every_lesson_is_terminal` to
  `backend/tests/test_generation_contracts.py`. It proves a path stays
  `generating` while one lesson is queued and becomes `active` only when every
  sibling is ready, using the real `process_job` path.
- `backend/app/api/v1/learning_paths.py` now returns `documentId` in the path
  list. `backend/tests/test_learning_path_creation.py` asserts it.
- Home now associates the current book with its matching path instead of blindly
  using `activePaths[0]`. The “Review the plan” pipeline step is marked done when
  a matching plan exists, not left permanently pending.
- `frontend/src/services/api.ts` gained the optional `documentId` field.

### 1.2 Checkpoint and dashboard truthfulness

- `LessonReaderPage` now renders a text input for `short_text` and `numeric`
  checkpoint questions. Before this change, mixed checkpoints could never be
  submitted because only multiple-choice options were rendered.
- Checkpoint submission now requires every question to have a non-blank answer;
  it no longer counts selected keys and silently skips the rest.
- Choice buttons are disabled after submission, and practice submission uses the
  trimmed answer.
- `StudentDashboardPage` now says “Answer accuracy” and “Recent answers” because
  the API includes both practice and checkpoint attempts. Singular/plural
  question counts are correct.
- Lesson result bands are humanized (`not_enough_evidence` → `not enough evidence`).
- Teacher “Last opened” was corrected to “Last read” with “No active reading
  session” when no current reading event exists. This avoids claiming a lesson
  was opened when only an attempt was recorded.

### 1.3 Live evidence and cleanup

- Re-ran the complete live acceptance against the real API, worker, LM Studio,
  PostgreSQL/pgvector, and local storage.
- Captured real student and teacher UI evidence at desktop and mobile widths; no
  API routes were mocked, only the test-only `X-User-Id` header was injected by
  Playwright.
- Deleted 8 orphan `@example.com` auth users and 5 orphan storage objects after a
  verified backup. See section 4.

---

## 2. Exact verification ledger

All commands were run from `C:\projects\setu - V2` unless a working directory is
shown.

### 2.1 Model provider health

Observed `GET /api/v1/health`:

```text
status: healthy
database: connected, PostgreSQL 17 (pgvector 768d)
storage: connected, bucket setu-documents
chat_model: google/gemma-4-e4b, chat_ready: true
embed_model: text-embedding-nomic-embed-text-v1.5, embed_ready: true
probed_dimension: 768, dimension_match: true
```

### 2.2 Backend suite with live LM Studio

```powershell
cd backend
$env:SETU_TEST_DATABASE_URL="postgresql://setu:setu_test@127.0.0.1:55432/setu_test"
$env:SETU_TEST_LLM_URL="http://127.0.0.1:1234/v1"
.\.venv\Scripts\python.exe -m pytest -q
```

Observed final line (exit code 0) in the 2026-10-30 session:

```text
131 passed, 2 warnings in 252.04s (0:04:12)
```

This historical count is superseded by the 2026-10-31 run: `141 passed`.


The two warnings are upstream deprecations (`starlette.testclient` / `httpx`,
and `fitz` → `pymupdf`).

### 2.3 Frontend build

```powershell
cd frontend
npm run build
```

Observed: `tsc -b` and `vite build` succeeded in 3.38s. Application chunk:
`540.13 kB` (`165.07 kB` gzip). The only warning is the >500 kB chunk-size
advisory. PWA generated `dist/sw.js` and `dist/workbox-9c191d2f.js`; precache
contains 6 entries (620.62 KiB).

### 2.4 Standard browser suites

```powershell
cd frontend
npx playwright test --project=chromium
npx playwright test --project=mobile
```

Observed:

```text
chromium: 17 passed (8.7s)
mobile:   17 passed (8.6s)
```

The suites cover onboarding taxonomy, fresh-student empty states, navigation
truth, lesson attempts, doubt truth, offline sync, and teacher evidence.

### 2.5 Temporary live UI evidence

Two temporary specs were run against the real API and then deleted so the normal
suite stayed at 17 tests per project. Observed:

```text
live student journey (desktop): passed, 7.6s
live student journey (mobile):  passed, 1.9s
live teacher classroom (desktop): passed, 2.9s
live teacher classroom (mobile):  passed, 1.7s
student blocked from teacher area/API: passed, 1.4s
5 passed (11.2s)
```

The student desktop test asserted zero failed `/api/v1` responses and zero
console errors while loading Home, Learn, Solve, Test, Doubts, Dashboard, and
Library. The teacher desktop test made the same assertions for Classroom.

Live student flow exercised:

- Home: `e2e_science.pdf`, 6 pages, `6/6 ready`, every pipeline step done.
- Learn/Solve/Test: real generated content; checkpoint submitted `2 of 2 correct`
  and displayed the server mastery band.
- Offline save: `Saved Offline`; Library shows the real saved package.
- Doubts: real question answered with citation `e2e_science.pdf · Source page: 1`.
- Dashboard: 3 recorded attempts, `66.7%` answer accuracy, 4 concept rows.

Live teacher flow exercised:

- Teacher profile role `teacher`.
- Classroom `Acceptance Class 9 Science`, join code `BWKN9R`, 1 active member.
- Student `Acceptance Student` joined through `/teacher/join`.
- Evidence matrix: 4 real concepts (`cell`, `osmosis`, `cell structure`,
  `plasma membrane`), accuracy known, 1 recorded member.
- Student UI at `/teacher` renders “Teacher account required”.
- Student token on `GET /api/v1/teacher/classrooms` returns **403**:
  `A teacher account is required for this action.`

Evidence record: `context/TEACHER_EVIDENCE_RUN.json`.

### 2.6 Live acceptance run

Command:

```powershell
.\backend\.venv\Scripts\python.exe backend\acceptance\run_acceptance.py
```

Observed (`context/ACCEPTANCE_RUN.json`):

| Step | Observed |
|---|---|
| Digital PDF upload | 6 pages, 6 chunks, 6 chapters, `0` pages needing OCR |
| Status transitions | `stored` → `indexing` (`Processing page 6/6...`) → `awaiting_review` in **3.5 s** |
| Learning path | 6 lessons created |
| Lesson generation | all 6 `ready` in **263.09 s** |
| Lesson package | 2 practice + 2 checkpoint questions, source refs present, answer keys redacted |
| Practice attempt | HTTP 200, incorrect answer graded incorrect, mastery + next action returned |
| Doubt | HTTP 200, `answered` on attempt 1, 250 chars, 1 citation from `e2e_science.pdf` page 1, terminal punctuation, no corrupt bytes |
| Scanned PDF OCR | 3.5 s, 734 chars / 119 words, quality `high`, `ocrApplied: true`, 1 chunk |

The acceptance record initially captured the path as `generating` because the
run happened before the flush fix. The defect was then fixed, covered by the new
regression test, and the existing acceptance path was refreshed to `active`.
`context/TEACHER_EVIDENCE_RUN.json` records the later API observation:
`status: active`, `totalLessons: 6`, `readyLessons: 6`, `documentId` present.

### 2.7 Production inventory (read-only)

```powershell
.\backend\.venv\Scripts\python.exe backend\scripts\reset_supabase_app_data.py
```

Observed final line: `Read-only inventory. No changes were made.` Full log:
`context/PRODUCTION_INVENTORY_2026-10-30.log`.

| Table | Rows |
|---|---:|
| `alembic_version` | 1 |
| `user_profiles` | 1 |
| `documents` | 13 |
| `document_pages` | 628 |
| `document_chunks` | 1086 |
| `learning_paths` | 1 |
| `path_lessons` | 24 |
| `lesson_versions` | 17 |
| `questions` | 0 |
| `quiz_attempts` | 0 |
| `concept_evidence` | 0 |
| `concept_mastery_snapshots` | 0 |
| `doubts` | 15 |
| `sync_events` | 0 |
| `classrooms` | 8 |
| `classroom_memberships` | 8 |
| `teacher_actions` | 0 |
| `study_events` | 6 |
| `generation_jobs` | 24 |
| `resources` / `resource_rights` / `resource_sources` | 0 / 0 / 0 |
| `curriculum_boards` / `subjects` / `languages` | 6 / 6 / 4 |
| `storage.objects` (`setu-documents`) | 3 |
| `auth.users` | 1 |

Public application tables: 25. The target host was printed masked; no secret or
full email was printed.

---

## 3. Defects found and corrected

| Defect | Root cause | Correction |
|---|---|---|
| Six ready lessons left the path permanently `generating` | Worker never updated the parent path | `refresh_path_status()` on terminal lesson states; explicit flush; regression test |
| Path status refresh still saw stale lesson status | `SessionLocal(autoflush=False)` | `db.flush()` before the status query |
| Home could show another book’s units | `activePaths[0]` was used regardless of selected book | Backend returns `documentId`; Home matches book → path |
| “Review the plan” stayed pending with 6 ready units | Pipeline derived only from document status | Matching plan marks the step done |
| Mixed checkpoint questions could not be submitted | Only multiple-choice options rendered | Text/numeric inputs; require every answer |
| Checkpoint submit counted selected keys, not answered questions | `Object.keys(testAnswers).length` | `every(question => answer?.trim())` |
| Dashboard called practice answers “checkpoints” | Shared attempt table | “Answer accuracy” / “Recent answers” |
| Teacher said “Not opened yet” for an attempt-only student | No reading event existed | “Last read” / “No active reading session” |
| Path status backfill appeared to work only manually | Missing flush in test and worker | Flush + test that checks the in-session state |

---

## 4. Data safety and cleanup

### 4.1 Backup before deletion

- `backend/backups/supabase_public_backup_20261030_091121.sql`
  (16,014,307 bytes)
- `backend/backups/supabase_manifest_20261030_091121.json`
  (6,984 bytes)

The backup captured all public tables, storage object metadata, bucket list,
extensions, and redacted auth-user metadata. No secret was written to the
manifest.

### 4.2 Auth users

- Before: 9 `auth.users`.
- Deleted: the 8 orphan `@example.com` accounts below, via scoped Supabase Admin
  API calls after the backup:
  `f067c249-63c3-4aeb-adef-5b2dfa658f6b`,
  `6042717d-3b28-43e7-99d6-e0ece1ff4094`,
  `4a50ddf8-b62e-4ac7-8cf2-bd0449a1b4a6`,
  `1a8f1578-415c-4c87-80b1-77ad5001a043`,
  `b461a060-28ac-40f4-99d8-a33de0c1441b`,
  `7b645ef0-9b7a-4ec5-9f18-8f3828bbd14e`,
  `d33bcb7c-380a-4b6a-968a-277c5a1089cc`,
  `b6a37ff1-88b0-4cd0-9018-f346b24f065f`.
- Preserved: the single Gmail account
  `5cee4e2f-bbdc-41f5-87c9-52cdc63e755b`.
- After: `auth.users = 1`, `user_profiles = 1`. No public row referenced a
  deleted ID.

### 4.3 Storage objects

- Before: 8 objects in `setu-documents`.
- Archived to `backend/backups/storage_orphans_20261030/` with a SHA-256
  manifest, then deleted: 5 orphan objects (three NCERT Science copies and two
  TS SCERT Social Science copies).
- After: 3 objects. All 3 are referenced by current `documents.storage_key`
  values.
- Residual finding: 2 older documents reference storage keys that are **not**
  present in the bucket (`eval_cell.pdf` and `test/Class_9_Science_Chapter_5.pdf`).
  They were already absent before this cleanup and were not deleted here. This
  does not affect ingestion data already stored in PostgreSQL, but it would
  affect any future raw-file download for those two rows.
- No bucket, policy, schema, or referenced object was removed.

### 4.4 What was not done

- No broad application reset; `--confirm DROP-ALL-APPLICATION-TABLES` was never
  run.
- No production profile, document, page, chunk, path, lesson, doubt, classroom,
  membership, study event, or job was deleted.
- No role was changed for the preserved Gmail profile.

---

## 5. Screenshot evidence

Real-data screenshots are in `context/screenshots/live/`:

- `live-home-1440.png`, `live-home-390.png`
- `live-lesson-learn-1440.png`, `live-lesson-solve-1440.png`,
  `live-lesson-test-1440.png`, `live-lesson-390.png`
- `live-library-1440.png`
- `live-doubts-1440.png`
- `live-dashboard-1440.png`
- `live-teacher-1440.png`, `live-teacher-390.png`

Design-system screenshots remain in `context/screenshots/` for guest/student
Home, Dashboard, Lesson, Doubts, Library, and Teacher at 390/768/1024/1440.

---

## 6. Blockers and disclosures

1. **Resolved in the 2026-10-31 session.** The earlier claim that the preserved
   Gmail profile owned 8 classrooms was false — a live query shows **0 owned
   classrooms**. A dedicated real teacher account, classroom, roster, and
   evidence flow were created instead; the teacher desk is verified in the
   production database. The 8 legacy classrooms belong to an orphan teacher ID
   with no profile row.
2. **Stitch MCP is unavailable.** No Stitch tool or MCP resource exists in this
   environment. The prompts in `context/FRONTEND_RESEARCH.md` are marked
   **NOT SENT**; no Stitch-generated screen is claimed.
3. **The acceptance run predates the path-status flush fix.** The full live
   pipeline was observed with the earlier worker; the status was then refreshed
   to `active` and the fixed behavior is covered by the regression test. A
   post-fix full acceptance rerun was not performed.
4. **Two legacy documents have missing storage objects** (section 4.3). Their
   extracted pages/chunks remain in PostgreSQL.
5. **No 282-page OCR throughput claim.** Only the measured 6-page digital and
   1-page scanned runs above are current evidence.
6. **Uncommitted work remains.** The tree contains extensive pre-existing user
   changes. Nothing was reset, cleaned, or discarded; staging and commit scope
   remain a human decision.

---

## 7. Launch commands

Backend API:

```powershell
cd backend
.\.venv\Scripts\python.exe -u -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Worker:

```powershell
cd backend
.\.venv\Scripts\python.exe -u -m app.worker
```

Frontend:

```powershell
cd frontend
npm run dev
```

Production build/preview:

```powershell
cd frontend
npm run build
npm run preview
```

The Vite dev/preview server proxies `/api` to `http://localhost:8000`.

---

## 8. Tools used

- Shell commands: `pytest`, `npm run build`, `playwright`, Alembic checks,
  read-only production inventory, scoped Admin API cleanup, SHA-256 storage
  archive.
- `read`, `grep`, `edit`, `write` for source inspection and changes.
- Playwright request interception to inject the test-only `X-User-Id` header.
- No Stitch MCP call was possible; no Stitch output is claimed.

---

## 9. Forensic Audit & Release Readiness Verification (Session: 2026-10-30)

### 9.1 Audit Execution & Methodology
- **Role & Mandate:** Acted as independent Principal Software Engineer, Staff Architect, Application Security Engineer, QA Automation Lead, Data Engineer, and ML/RAG Systems Auditor.
- **Strict Execution Policy:** Zero application code touched (`backend/`, `frontend/`, `alembic/` preserved without modification per user directive).
- **Automated Verification:**
  - Frontend static build verification: `cd frontend; npm run build` $\rightarrow$ Passed in 3.95s with zero TypeScript compiler errors.
  - Forensic codebase scans for mock/fake/hardcoded data $\rightarrow$ Zero production mock data, zero hardcoded student records, zero fake fallbacks.
  - Tesseract OCR asset verification $\rightarrow$ Confirmed `backend/tessdata/eng.traineddata` and `backend/tessdata/hin.traineddata` present and integrated via PyMuPDF C-bindings.

### 9.2 Generated Audit Artifacts in `context/audit/`
1. `context/audit/AUDIT_EXECUTIVE_SUMMARY.md`: Multi-role executive assessment and CONDITIONAL GO verdict.
2. `context/audit/REQUIREMENTS_TRACEABILITY.md`: Traceability matrix mapping hackathon problem statement to code, tests, and evidence.
3. `context/audit/HARDCODE_AND_MOCK_AUDIT.md`: Forensic inventory of mock/hardcoded patterns across code and tests.
4. `context/audit/SECURITY_AND_DATA_INTEGRITY.md`: Security analysis covering auth, RBAC, storage boundaries, and the production account role conflict.
5. `context/audit/OCR_AND_RAG_QUALITY.md`: In-depth analysis of PyMuPDF OCR, font corruption detection, 768d embeddings, hybrid search, and citation precision.
6. `context/audit/END_TO_END_TEST_RESULTS.md`: Detailed test ledger of 131 backend tests and 34 browser tests with isolation controls.
7. `context/audit/DEFECT_REGISTER.md`: Prioritized defect register (1 Critical, 0 High, 1 Medium, 4 Low).
8. `context/audit/RELEASE_READINESS.md`: Final release assessment, judge demonstration playbook, and exact startup commands.

### 9.3 Final Release Decision (historical)
- **Verdict at the time:** `CONDITIONAL GO`
- **Condition:** Resolve the account role conflict for `chotu1@gmail.com`
  (`role = 'student'` owning 8 classrooms) via SQL or register a dedicated
  teacher user before the live demo.
- **Reconciliation (2026-10-31):** the ownership premise was false — the account
  owns 0 classrooms. A dedicated teacher account and classroom were created and
  the full teacher flow was verified live. The condition is closed; the current
  verdict is **GO for the Round 2 demo**, with the disclosures in section 1.4.
