# SETU Acceptance Matrix

**Last updated:** 2026-10-31 (Round 2 adaptive plan, coaching, smart checks, teacher class-gap flow, final suites)
**Rule:** only observed results are listed. A mocked browser test proves the UI
contract, not a live provider or live extraction. A live flow is only marked
**Pass** when the named API, worker, database, and provider were actually
running. Rows that still lack a live layer are **Partial**, **Blocked**, or
**Not run**.

## Status legend

| Status | Meaning |
|---|---|
| **Pass** | Executed in this repository with the recorded command/assertion and the result was observed. |
| **Partial** | One layer is proven (contract, static audit, or mocked UI), but the full live flow was not exercised. |
| **Blocked** | Cannot be executed until a named external dependency or approval is available. |
| **Not run** | No execution was attempted in this verification session. |

## Matrix

| # | Acceptance flow | Status | Observed evidence | Gap / next action |
|---|---|---|---|---|
| 1 | Fresh student and teacher start with empty, truthful state | **Pass** | `test_fresh_account_clean_state.py` (1); `test_catalogue_and_profile_defaults.py` (3); `test_student_dashboard_truth.py` (5). Fresh profiles have no invented board, grade, goal, resources, classrooms, attempts, or mastery. | None. |
| 2 | Taxonomy comes from the API and invalid academic context is rejected | **Pass** | `test_taxonomy_validation.py` (9); Playwright `onboarding_taxonomy.spec.ts` 2/2 on chromium and mobile. Production inventory shows 6 boards, 6 subjects, 4 languages. A failed load disables saving and offers retry. | None. |
| 3 | Guests cannot reach protected student/teacher screens; unknown routes are real | **Pass** | Playwright `navigation_truth.spec.ts` 2/2 on both projects: guest nav exposes only Home, `/dashboard` asks for sign-in, unknown route renders `Page not found`. | None. |
| 4 | Server grades practice and checkpoints; clients cannot force correctness | **Pass** | `test_attempt_grading.py` (6); `test_lesson_package_redaction.py` (2); live practice attempt graded incorrect; live checkpoint submitted `2 of 2 correct` with server mastery. Playwright `lesson_attempts.spec.ts` 2/2. | None. |
| 5 | Online doubt answers immediately; provider failures are retryable | **Pass** | Live doubt: HTTP 200, `answered` on attempt 1, 250 chars, 1 citation from `e2e_science.pdf` page 1, terminal punctuation, no corrupt bytes. `test_doubt_truth.py` (3); Playwright `doubt_truth.spec.ts` 5/5 proves retry without offline enqueue. | Provider failure is covered by a mocked 5xx contract test, not by killing the live model. |
| 6 | Only genuine browser-offline events queue; reconnect sync is idempotent | **Pass** | `test_idempotent_sync.py` (1); Playwright `offline_sync.spec.ts` 2/2 on both projects and the offline doubt case. The browser context was taken offline; no physical network adapter was unplugged. | None. |
| 7 | Teacher evidence is scoped to owned classrooms and recommendations need evidence | **Pass** | Live teacher API: classroom 200, roster 200 with 1 active member, evidence matrix 200 with 4 real concepts. Student token on `/teacher/classrooms` → **403**. Student UI at `/teacher` → “Teacher account required”. Playwright `teacher_evidence.spec.ts` 2/2. | Production teacher screens remain blocked by the preserved account’s `student` role (row 18). |
| 8 | Durable queue claims jobs atomically and recovers expired leases | **Pass** | `test_worker_recovery.py` (1); generation contract tests; live worker processed all 6 queued lesson jobs to `ready`. New regression test proves the parent path becomes `active` only after every lesson is terminal. | Lease recovery was tested with a real database session, not by killing a production worker. |
| 9 | Extraction never embeds unreadable or corrupted pages; failed embeddings leave no partial index | **Pass** | `test_ingestion_quality.py` (4); `test_extraction.py` (8, including Tesseract OCR, corrupted symbol font, NUL bytes, PPTX). Live scanned page: 734 chars/119 words, quality `high`, `ocrApplied: true`. | No current 282-page throughput measurement; do not cite the old 0.39 s/page figure. |
| 10 | Lesson publication validates source references, questions, and visual specs | **Pass** | Live: 6/6 lessons `ready`; package has 2 practice + 2 checkpoint questions, source refs, redacted answer keys, valid validation block. `test_lesson_validator.py` (2); `test_generation_contracts.py` (7). | Live package contained 0 visuals, so visual-spec rendering is covered separately in row 11. |
| 11 | Visuals never fabricate unspecified content | **Partial** | Static audit removed hardcoded ConceptMap nodes, CoordinateGrid points, FractionModel `3/4`, NumberLine ranges, and CellMembrane labels. Missing data renders `VisualUnavailable`. `npm run build` passes. | The live generated lesson had no visual block, so no visual was rendered from real data. Needs a live lesson with at least one visual. |
| 12 | Production inventory is inspected read-only and scoped cleanup is recoverable | **Pass** | Read-only inventory: 1 profile, 13 documents, 628 pages, 1086 chunks, 1 path, 24 lessons, 17 versions, 15 doubts, 8 classrooms, 8 memberships, 6 study events, 24 jobs, 0 resources/rights, 3 storage objects, 1 auth user. Backup: 16,014,307-byte SQL + 6,984-byte manifest. 8 orphan auth users and 5 orphan storage objects deleted after archive; every remaining object is referenced. | 2 legacy documents still reference absent storage objects (`eval_cell.pdf`, `test/Class_9_Science_Chapter_5.pdf`); pre-existing, recorded in the cleanup report. |
| 13 | Emergency reset refuses unless all three gates are present | **Pass** | `test_reset_guard.py` (4). Gates: exact confirmation, non-empty backup, production acknowledgement. | Destructive path not run, by design. |
| 14 | Static build, backend suite, and browser suites are healthy | **Pass** | `npm run build` succeeded (3.38s; only >500 kB warning); `pytest -q` = **131 passed** in 252.04s with live LM Studio; chromium **17 passed** (8.7s); mobile **17 passed** (8.6s). | None. |
| 15 | Real grounded answer with page citations from the configured model | **Pass** | Live LM Studio `google/gemma-4-e4b`, embedding 768d. Doubt answered on first attempt with 1 real citation and page range from the uploaded PDF. Answer ends with terminal punctuation; no corrupt bytes. | Answer quality varies by model; no claim of universal grounding. |
| 16 | Live upload → OCR → chunks → outline → ready lesson → practice | **Pass** | Digital PDF: `stored` → `indexing` → `awaiting_review` in 3.5s, 6 pages/6 chunks/6 chapters; all 6 lessons ready in 263.09s; practice attempt graded; scanned PDF OCR in 3.5s. | The captured run recorded the path as `generating` before the flush fix. The fixed refresh was verified by regression test and the same path then observed `active` with 6/6 ready. A full post-fix rerun was not performed. |
| 17 | Mobile and tablet responsive acceptance | **Pass** | Mobile Playwright **17 passed**; live student Home/Lesson and teacher Classroom captured at 390px with no failed API calls in the student/teacher desktop checks. Tablet design screenshots exist at 768/1024. | Tablet is visual inspection, not an automated tablet project. |
| 18 | Live teacher classroom lifecycle (create → rotate → enroll → evidence → recommendation response) | **Partial** | Live in the disposable test DB: teacher profile, classroom creation, join code `BWKN9R`, student join, roster, evidence matrix, and student 403 all observed. `test_teacher_classroom_management.py` covers rotate/remove/restore. | Code rotation and sending a recommendation were not exercised against the live API; production teacher screens are blocked by the Gmail profile’s `student` role. |

## Summary

| Status | Count |
|---|---:|
| Pass | 16 |
| Partial | 2 |
| Blocked | 0 |
| Not run | 0 |
| **Total** | **18** |

## What is explicitly not claimed

- The earlier claim that the preserved Gmail profile owns 8 classrooms was false
  (live query: 0). A dedicated teacher account, classroom, roster, evidence
  matrix, class-gap radar, and recommendation delivery were verified live; see
  `STATUS_REPORT.md` section 1.2.
- No claim of 100% acceptance.
- No claim of 282-page OCR throughput; only the measured 6-page digital and
  1-page scanned runs are current.
- No claim that a visual block rendered live; the live package had zero visuals.
- No claim that teacher code rotation was exercised live; that remains
  contract/mocked-UI evidence.
- No claim that the two legacy documents with absent storage objects can be
  downloaded.
- No claim that Stitch MCP was used; it is unavailable and the prompts are marked
  **NOT SENT**.
- No claim that a post-path-fix full acceptance rerun occurred; the fix is
  covered by a regression test plus a live API observation of `active`.
- No claim that the production database was broadly reset; only scoped auth and
  orphan storage objects were removed after backup.
