# SETU Acceptance Matrix

**Last updated:** 2026-10-29 (Task 17 final verification)
**Rule:** only observed results are listed. A mocked browser test proves the UI
contract, not a live provider or live extraction. Rows that need a running model,
a worker, or a real account are marked **Blocked** or **Not run**, not passed.

## Status legend

| Status | Meaning |
|---|---|
| **Pass** | Executed in this repository with the recorded test/command and the assertion passed. |
| **Partial** | One layer is proven (API contract or mocked UI), but the full live flow was not exercised. |
| **Blocked** | Cannot be executed until a named external dependency is available. |
| **Not run** | No execution was attempted in this verification session. |

## Matrix

| # | Acceptance flow | Status | Observed evidence | Gap / next action |
|---|---|---|---|---|
| 1 | Fresh student and teacher start with empty, truthful state | **Pass** | `backend/tests/test_fresh_account_clean_state.py` (1 passed); `test_catalogue_and_profile_defaults.py` (3 passed); `test_student_dashboard_truth.py` (5 passed). New profiles have no invented board, grade, goal, resources, classrooms, attempts, or mastery. | None. |
| 2 | Taxonomy comes from the API and invalid academic context is rejected | **Pass** | `backend/tests/test_taxonomy_validation.py` (9 passed); Playwright `onboarding_taxonomy.spec.ts` 2/2; `student_dashboard_truth.spec.ts` 2/2. Board/language lists render from mocks, and a failed taxonomy load disables saving. | Live catalogue contents were not re-verified against production; the API is the source. |
| 3 | Guests cannot reach protected student/teacher screens; unknown routes are real | **Pass** | Playwright `navigation_truth.spec.ts` 2/2: guest navigation exposes only Home; `/dashboard` asks for sign-in; unknown route renders `Page not found`. | None. |
| 4 | Server grades practice and checkpoints; clients cannot force correctness | **Pass** | `backend/tests/test_attempt_grading.py` (6 passed); `test_lesson_package_redaction.py` (2 passed); Playwright `lesson_attempts.spec.ts` 2/2. | Live lesson content depends on generation (row 16). |
| 5 | Online doubt answers immediately; provider failures are retryable | **Partial** | `backend/tests/test_doubt_truth.py` (3 passed) proves retry state, no citations on insufficient evidence, and blank-question rejection; Playwright `doubt_truth.spec.ts` 5/5 proves immediate online submit, retry, and no offline enqueue on a provider failure. | The model itself was not running, so no real generated answer/citation was observed. See row 15. |
| 6 | Only genuine browser-offline events queue; reconnect sync is idempotent | **Pass** | Playwright `offline_sync.spec.ts` 2/2 and `doubt_truth.spec.ts` offline case; `backend/tests/test_idempotent_sync.py` (1 passed). | Real device network loss was simulated by the browser context, not by unplugging a network. |
| 7 | Teacher evidence is scoped to owned classrooms and recommendations need evidence | **Pass** | `backend/tests/test_teacher_evidence_scope.py` (3 passed); `test_authorization.py` (4 passed); `test_multi_user_evidence_matrix.py` (1 passed); Playwright `teacher_evidence.spec.ts` 2/2. | The preserved production Gmail account has role `student` while owning classrooms, so live teacher screens return 403 until the role is corrected. |
| 8 | Durable queue claims jobs atomically and recovers expired leases | **Pass** | `backend/tests/test_worker_recovery.py` (1 passed); `test_generation_contracts.py` (6 passed); worker entry `python -m app.worker` exists. | A real worker was not run against production in this session. |
| 9 | Extraction never embeds unreadable or corrupted pages; failed embeddings leave no partial index | **Pass** | `backend/tests/test_ingestion_quality.py` (4 passed); `test_extraction.py` (8 passed, including Tesseract OCR, corrupted symbol font, NUL bytes, PPTX, large multipage scaling). | No live 282-page throughput measurement was taken in this session; the old 0.39 s/page claim is not current evidence. |
| 10 | Lesson publication validates source references, questions, and visual specs | **Pass** | `backend/tests/test_lesson_validator.py` (2 passed); `test_generation_contracts.py` (6 passed); `test_recovery_contracts.py` (7 passed). | Live generated lesson content is blocked by row 16. |
| 11 | Visuals never fabricate unspecified content | **Pass** | Source audit: hardcoded ConceptMap nodes, CoordinateGrid points, FractionModel `3/4`, NumberLine range/highlight, and CellMembrane labels were removed. Each visual now renders `VisualUnavailable` when its required spec data or alt text is missing. `npm run build` passes. | No dedicated Playwright assertion for each visual type; static audit only. |
| 12 | Production inventory is inspected read-only and scoped cleanup is recoverable | **Pass** | `reset_supabase_app_data.py` default run printed 25 public tables, 1 profile, 13 documents, 628 pages, 1086 chunks, 1 path, 24 lessons, 17 versions, 0 questions/attempts, 15 doubts, 8 classrooms, 8 memberships, 6 study events, 24 jobs, 0 resources/rights, 8 storage objects, 9 auth users, and stated “Read-only inventory. No changes were made.” | Nine `auth.users` rows exist for one profile. Orphan auth users were not deleted; that needs an explicit decision. |
| 13 | Emergency reset refuses unless all three gates are present | **Pass** | `backend/tests/test_reset_guard.py` (4 passed). Gates: exact confirmation, non-empty backup, production acknowledgement. | The destructive path was not run, by design. |
| 14 | Static build, backend suite, and Chromium browser suite are healthy | **Pass** | `npm run build` succeeded (only the >500 kB chunk warning); `pytest -q` = `104 passed, 6 skipped`; `npx playwright test --project=chromium` = `17 passed`; Alembic `current`/`heads` both `007 (head)`. | The six skips are LLM integration tests that require `SETU_TEST_LLM_URL`. |
| 15 | Real grounded answer with page citations from the configured model | **Blocked** | Health/provider integration was not executed because LM Studio at `http://127.0.0.1:1234/v1` was not verified running with `google/gemma-4-e4b` and `text-embedding-nomic-embed-text-v1.5`. | Start LM Studio, confirm `probed_dimension: 768` on `/api/v1/health`, set `SETU_TEST_LLM_URL`, then run the six skipped integration tests and one live doubt. |
| 16 | Live upload → OCR → chunks → outline → ready lesson → practice | **Blocked** | Upload/extraction/path/lesson layers pass separately in tests, but no live upload was executed against the running API + worker + model stack in this session. | Start API + worker + model; upload one real document; record page quality, chunk count, lesson validation, and one graded attempt. |
| 17 | Mobile and tablet responsive acceptance | **Not run** | `playwright.config.ts` defines a `mobile` project, but only `--project=chromium` was executed. | Run `npx playwright test --project=mobile`; capture screenshots and any layout defects. |
| 18 | Live teacher classroom lifecycle (create → rotate code → enroll → evidence → recommendation response) | **Partial** | Contract and mocked-UI evidence in row 7. Backend creates real join codes and scopes evidence to the owning teacher. | The preserved account role mismatch blocks the live teacher screens. Correct the role or use a real teacher account, then run the lifecycle. |

## Summary

| Status | Count |
|---|---:|
| Pass | 13 |
| Partial | 2 |
| Blocked | 2 |
| Not run | 1 |
| **Total** | **18** |

## What is explicitly not claimed

- No claim of 100% acceptance.
- No claim of live model grounding or citation quality.
- No claim of live 282-page OCR throughput.
- No claim that the production account can use teacher screens.
- No claim that mobile layouts pass.
- No claim that orphan auth users were cleaned up.
