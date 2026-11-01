# SETU Status Report

**Session date:** 2026-10-29
**Scope:** Clean-real-product Tasks 15–17, final backend/browser verification
**Workspace:** `C:\projects\setu - V2`
**Visible product name:** SETU (no version suffix in UI, titles, or manifests)
**HEAD at session start:** `8d2b00f` (`fix: guard routes and make navigation, visuals, and copy truthful`)
**Task 17 commit:** `chore: guard destructive reset and record truthful acceptance evidence` (the commit containing this report).

---

## 1. What changed

### Task 15 — Academic taxonomy from the API

- Added server-side validation for boards, subjects, languages, grades, and
  classroom academic context in `backend/app/api/v1/auth.py`,
  `profile.py`, and `teacher.py`.
- Added `backend/tests/test_taxonomy_validation.py` (9 tests).
- Added `frontend/src/hooks/useTaxonomy.ts` and
  `frontend/src/lib/academic.ts`; `GRADES` / `gradeLabel` are the only shared
  class list.
- `AuthModal`, `OnboardingTour`, `StudentDashboardPage`, and
  `TeacherDashboardPage` now load boards/subjects/languages from the API.
- A failed taxonomy load shows an error, disables the dependent controls, and
  offers Retry. No CBSE/English/Class 9 defaults are injected.
- `ProfileUpdateRequest` no longer accepts `role`, so a profile cannot escalate
  itself.
- Added `frontend/e2e/onboarding_taxonomy.spec.ts` (2 tests) and extended
  `student_dashboard_truth.spec.ts`.

### Task 16 — Truthful routes, navigation, visuals, and copy

- Added `AuthGate` and `NotFoundPage`; protected routes now require sign-in and
  the catch-all route renders a real page.
- Guest navigation exposes only Home. Student/teacher links appear only when the
  account can use them.
- Unit rows on Home are real buttons, disabled unless the lesson is `ready`.
- Download and offline-save actions now show success, failure, and in-progress
  states instead of swallowing errors.
- `science_process` visuals no longer render cell-membrane art. The renderer
  requires real process steps and otherwise states the visual is unavailable.
- Removed overclaims: “verified textbooks”, “zero hallucinations”, “Verified
  Textbook Citation”, and a hardcoded “Class 9 Textbook” fallback now use
  source-neutral wording and real document metadata.
- API title/version is `SETU` / `1.0.0`; the PWA manifest description is
  source-grounded and version-free.
- Added `docs/UI_ACTION_AUDIT.md` and `frontend/e2e/navigation_truth.spec.ts`.
- Deleted the stale `frontend/e2e/setu_full_e2e.spec.ts`.

### Task 17 — Guarded reset, truthful state, final verification

- Rewrote `backend/scripts/reset_supabase_app_data.py` so importing it has no
  side effects and `main()` owns all database work.
- The destructive reset now requires all three gates:
  `--confirm DROP-ALL-APPLICATION-TABLES`, a non-empty `--backup`, and
  `--allow-production SETU-PRODUCTION-RESET`.
- Default mode is a read-only inventory. It masks the target host and never
  prints the database URL, password, or service key.
- Added `backend/tests/test_reset_guard.py` (4 tests) and
  `backend/tests/test_fresh_account_clean_state.py` (1 test).
- Changed the production doubt prompt from “Verified Textbook Evidence” to
  “Source Evidence from the Uploaded Document”; the insufficient-evidence
  answer now says the source does not contain enough evidence.
- Removed fabricated defaults from `ConceptMap`, `CoordinateGrid`,
  `FractionModel`, `NumberLine`, and `CellMembrane`. Missing or invalid spec
  data now renders `VisualUnavailable` instead of invented nodes, points,
  fractions, ranges, or labels.
- Added `docs/OPERATIONS.md`, rewrote `context/ACCEPTANCE_MATRIX.md`, and
  updated `context/SUPABASE_CLEANUP_MANIFEST.md` with the final inventory.

---

## 2. Root causes corrected

| Defect | Root cause | Correction |
|---|---|---|
| Onboarding and profile forms showed CBSE/English/Class 9 even when the API had no such data | Hardcoded select options and default state | API-driven `useTaxonomy`; empty initial selection; server validation before writes |
| Guests could open protected pages | Routes were not guarded; sidebar showed all links | `AuthGate`; guest nav only Home; catch-all not-found route |
| Unit rows were mouse-only and looked enabled while queued | Click handler on `<li>` | Real `<button>` with native `disabled` unless `ready` |
| Download failures were silent | `saveLessonOffline` rejection was unhandled or only logged | Visible success/error state on Home and Lesson |
| Cell-membrane art appeared for unrelated processes | `science_process` fell through to `CellMembrane` | Dedicated `ProcessDiagram`; unavailable message when steps are missing |
| Visual components invented content | Hardcoded default nodes, points, fraction, range, labels | Required spec data; `VisualUnavailable` otherwise |
| Copy claimed “verified textbooks” and “zero hallucinations” | Marketing copy outran the implementation | Source-grounded wording; real document metadata |
| Reset script ran on import with one weak gate | Module-level side effects and a single confirmation | Import-safe `main()`, three gates, read-only default, timestamped reports |
| Doubt prompt called retrieved passages “verified textbook evidence” | Legacy textbook-specific prompt | Source-neutral prompt and abstention wording |

---

## 3. Exact verification ledger

All commands were run from `C:\projects\setu - V2` unless a working directory is
shown.

### 3.1 Alembic on the disposable test database

```powershell
$env:DATABASE_URL="postgresql://setu:setu_test@127.0.0.1:55432/setu_test"
.\backend\.venv\Scripts\alembic.exe -c backend\alembic.ini upgrade head
.\backend\.venv\Scripts\alembic.exe -c backend\alembic.ini current
.\backend\.venv\Scripts\alembic.exe -c backend\alembic.ini heads
```

Observed:

```text
007 (head)
007 (head)
```

`upgrade head` reported no pending revision; `current` and `heads` both resolve
to `007`. The test database container `backend-postgres-test-1` was healthy at
`127.0.0.1:55432`.

### 3.2 Backend suite

```powershell
cd backend
$env:SETU_TEST_DATABASE_URL="postgresql://setu:setu_test@127.0.0.1:55432/setu_test"
.\.venv\Scripts\python.exe -m pytest -q
```

Observed final line:

```text
104 passed, 6 skipped, 2 warnings in 7.23s
```

A `-rs` run listed the six skips, all with the same reason:

```text
integration test requires SETU_TEST_LLM_URL and a live model server
```

The six skips are one vertical-slice test and five RAG integration tests. They
were not converted into passes.

### 3.3 Frontend build

```powershell
cd frontend
npm run build
```

Observed: `tsc -b` and `vite build` succeeded. The only warning is the
>500 kB application chunk. The PWA generated `dist/sw.js` and
`dist/workbox-9c191d2f.js`; precache contained 6 entries (573.97 KiB).

### 3.4 Browser suite

```powershell
cd frontend
npx playwright test --project=chromium
```

Observed final line:

```text
17 passed (11.3s)
```

Coverage: onboarding taxonomy (2), student dashboard truth (2), navigation
truth (2), lesson attempts (2), doubt truth (5), offline sync (2), teacher
evidence (2).

The `ECONNREFUSED` lines printed by the preview proxy are expected for requests
that a spec did not mock. They did not fail any assertion.

### 3.5 Production inventory (read-only)

```powershell
.\backend\.venv\Scripts\python.exe backend\scripts\reset_supabase_app_data.py
```

Observed final line: `Read-only inventory. No changes were made.`

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
| `resources` | 0 |
| `resource_rights` | 0 |
| `resource_sources` | 0 |
| `curriculum_boards` | 6 |
| `subjects` | 6 |
| `languages` | 4 |
| `storage.objects` (`setu-documents`) | 8 |
| `auth.users` | 9 |

Public application tables: 25. The target host was printed masked; no secret or
full email address was printed.

---

## 4. Data safety

- **No broad reset was run.** The emergency reset was not invoked with
  `--apply`.
- The earlier Task 2 scoped cleanup deleted eight `example.com` profiles and the
  26 seeded resource/rights rows, while preserving the Gmail profile
  `5cee4e2f-bbdc-41f5-87c9-52cdc63e755b`.
- Task 17's inventory was read-only and changed no rows, storage objects, or
  auth users.
- Pre-existing uncommitted user work remains in the tree. Task 17 files are
  staged explicitly; `git add .`, `git reset`, `git checkout --`, `git restore`,
  and `git clean` were not used.

---

## 5. OCR and extraction evidence

- `backend/tests/test_extraction.py` (8 tests) proves PDF text extraction, NUL
  byte stripping, plain text, corrupted-symbol-font detection, Tesseract OCR on
  a scanned image page, large multipage scaling, PPTX slides, and an uploaded
  Class 10 English book sample.
- `backend/tests/test_ingestion_quality.py` (4 tests) proves unreadable documents
  become `needs_ocr`, failed embeddings leave no partial chunks, and only valid
  768-dimensional vectors are indexed.
- **No new throughput measurement was taken in this session.** The historical
  “282 pages / 0.39 s per page” claim is not re-verified and must not be cited as
  current evidence. A measured run is part of the next mission.
- **No screenshots were captured in this session.** Screenshot evidence is
  pending the frontend acceptance pass.

---

## 6. Blockers

1. **LM Studio is not verified running.** Grounded answers, citations, live
   lesson generation, and the six integration tests need
   `http://127.0.0.1:1234/v1` with `google/gemma-4-e4b` and
   `text-embedding-nomic-embed-text-v1.5`, plus a 768-dimension probe.
2. **Six integration tests are skipped** until `SETU_TEST_LLM_URL` points to a
   live compatible server.
3. **The preserved Gmail profile has role `student` but owns 8 classrooms.**
   Teacher-role-gated endpoints return 403 until the role is corrected or a real
   teacher account is used.
4. **Eight orphan `auth.users` rows remain** for one `user_profiles` row after
   the scoped cleanup. They were not deleted without explicit approval and a
   verified backup.
5. **Mobile browser acceptance was not run.** Only the Chromium desktop project
   was executed.
6. **No live upload → extraction → path → lesson → practice run was performed**
   in this session. The layers pass separately.
7. **Pre-existing uncommitted changes remain in the working tree.** They were
   preserved and not attributed to this task.

---

## 7. Next action

Start the product-hardening mission in this order:

1. Verify LM Studio connectivity and the 768-dimension contract; run the six
   skipped integration tests.
2. Upload one real document through the API and worker; record page quality,
   OCR flags, chunk counts, embedding results, and progress transitions.
3. Fix any upload visibility, extraction quality, durable-worker, progress,
   path-readiness, online-doubt, or teacher-authorization defects found by that
   run.
4. Run production truth scans for fabricated data, overclaims, and dead
   controls.
5. Commission the dedicated frontend research pass with Stitch MCP, then remake
   the frontend in React 19 + Vite + TypeScript + CSS Modules around the real
   APIs and states.
6. Run full desktop and mobile acceptance, capture screenshots, and update this
   report and `context/ACCEPTANCE_MATRIX.md` with observed results only.

---

## 8. Tools used

- Shell commands (`pytest`, `alembic`, `npm run build`, `playwright`, and the
  read-only inventory script).
- `read`, `grep`, `edit`, and `write` for source inspection and changes.
- No subagent was used for Tasks 15–17.
- No Stitch MCP call was made in this session; the frontend remake and its
  research pass are still pending.
