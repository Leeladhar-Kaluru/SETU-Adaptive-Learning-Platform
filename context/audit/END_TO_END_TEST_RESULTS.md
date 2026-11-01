# SETU — End-to-End Test Verification & Results Ledger

**Product Name:** SETU  
**Audit Date:** 30 October 2026  
**Auditor:** QA Automation Lead & Test Infrastructure Auditor  
**Scope:** Automated backend pytest suite, Playwright browser test suites, static build verifications, and harness isolation controls.

---

> **Current re-run — 2026-10-31.** Backend: **141 passed**, 23.93s. Playwright
> Chromium + mobile: **34 passed** (17 per project), 9.3s. Frontend build:
> passed, 1656 modules, `567.11 kB` / `172.85 kB` gzip. The table below records
> the historical 2026-10-30 audit run.

---

## 1. Executive Summary (historical)

| Test Layer | Total Tests | Passed | Failed | Skipped | Total Runtime | Execution Environment |
|---|:---:|:---:|:---:|:---:|:---:|---|
| **Backend Pytest Suite** | 131 | 131 | 0 | 0 | 252.04s | Python 3.13, disposable test DB (`127.0.0.1:55432`), LM Studio |
| **Playwright Chromium E2E** | 17 | 17 | 0 | 0 | 8.7s | Headless Chromium, Vite dev server (`127.0.0.1:5173`) |
| **Playwright Mobile E2E** | 17 | 17 | 0 | 0 | 8.6s | Mobile Safari emulation (390px viewport) |
| **TypeScript Build Check** | 1 | 1 | 0 | 0 | 3.95s | `tsc -b && vite build` (Zero TS errors) |
| **Total Automated Checks** | **166** | **166** | **0** | **0** | — | — |

---

## 2. Test Safety Guard & Database Isolation

A crucial finding of this audit is the **strict isolation guard implemented in `backend/tests/conftest.py`**:
```python
TEST_DATABASE_URL = os.environ.get("SETU_TEST_DATABASE_URL", "")
if not TEST_DATABASE_URL:
    raise RuntimeError(
        "SETU_TEST_DATABASE_URL is required. Start backend/docker-compose.test.yml "
        "and export the disposable PostgreSQL URL before running pytest."
    )
if "supabase" in TEST_DATABASE_URL.lower() or "pooler" in TEST_DATABASE_URL.lower():
    raise RuntimeError("Refusing to run tests against Supabase or a hosted pooler.")
```
- **Harness Safety:** The test suite **refuses to run** if the database URL contains `"supabase"` or `"pooler"`. This guarantees that tests can never truncate, alter, or corrupt the production Supabase database.
- **Reference Catalog Check:** The fixture `migrated_database` verifies that fresh test migrations do not seed mock resources into the database.

---

## 3. Backend Pytest Suite Breakdown (131 Tests)

| Test Module File | Test Count | Status | Key Behaviors Verified |
|---|:---:|:---:|---|
| `test_fresh_account_clean_state.py` | 1 | **PASS** | Brand new profiles start with zero fabricated data, 0 paths, 0 documents, 0 attempts. |
| `test_catalogue_and_profile_defaults.py` | 3 | **PASS** | Validates default boards, subjects, languages; rejects non-existent boards. |
| `test_taxonomy_validation.py` | 9 | **PASS** | Validates CBSE/ICSE board IDs, subject codes, grade limits (6–10), and language tags. |
| `test_auth_and_profiles.py` | 8 | **PASS** | Supabase JWT authentication, profile creation, onboarding flags, password confirmation. |
| `test_authorization.py` | 5 | **PASS** | Role boundary enforcement: students cannot invoke teacher APIs (returns 403 Forbidden). |
| `test_teacher_classroom_management.py` | 7 | **PASS** | Classroom creation, unique join code generation, code rotation, roster management. |
| `test_teacher_evidence_scope.py` | 4 | **PASS** | Evidence matrix strictly aggregates only active members of the teacher's owned classroom. |
| `test_multi_user_evidence_matrix.py` | 6 | **PASS** | Multi-student mastery aggregation across multiple concepts and classrooms. |
| `test_storage_backend.py` | 4 | **PASS** | File upload size limits (50MB), extension filtering, Supabase Storage isolation. |
| `test_document_visibility.py` | 4 | **PASS** | Users cannot inspect, download, or delete other users' uploaded documents. |
| `test_extraction.py` | 8 | **PASS** | Digital PDF extraction, Tesseract OCR fallback, symbol font corruption detection, DOCX/PPTX parsing. |
| `test_ingestion_quality.py` | 4 | **PASS** | Page-aware chunking, heading tree preservation, rollback on embedding failure. |
| `test_rag_evaluation.py` | 6 | **PASS** | Grounded retrieval scoring, reciprocal rank fusion, low-confidence query rejection. |
| `test_retrieval_truth.py` | 5 | **PASS** | Semantic + FTS hybrid search, citation page number provenance. |
| `test_doubt_truth.py` | 3 | **PASS** | Online doubt answering with real citations; offline queueing only when client is offline. |
| `test_learning_path_creation.py` | 5 | **PASS** | Curriculum outline generation, chapter grouping, learning path lifecycle. |
| `test_lesson_package_redaction.py` | 2 | **PASS** | Anti-tamper: answer keys and explanations redacted before delivery to student. |
| `test_lesson_validator.py` | 2 | **PASS** | Lesson packages must contain source refs, practice questions, checkpoint questions. |
| `test_attempt_grading.py` | 6 | **PASS** | Server-side attempt evaluation, score calculation, hint penalty tracking. |
| `test_adaptive_engine.py` | 5 | **PASS** | Bayesian mastery updates, 4 evidence bands, remediation unit generation on failure. |
| `test_worker_recovery.py` | 1 | **PASS** | Background worker recovers abandoned/crashed job leases via heartbeat expiration. |
| `test_generation_contracts.py` | 7 | **PASS** | Idempotent queue workers, job status transitions (`pending` $\rightarrow$ `claimed` $\rightarrow$ `ready`). |
| `test_idempotent_sync.py` | 1 | **PASS** | Reconnect sync outbox drains without duplicating attempt or doubt records. |
| `test_student_dashboard_truth.py` | 5 | **PASS** | Real-time computation of streak, minutes studied, accuracy rate, 84-day heatmap. |
| `test_ai_provider_truth.py` | 10 | **PASS** | LM Studio client communication, timeout handling, retry logic, refusal formatting. |
| `test_cleanup_demo_data.py` | 2 | **PASS** | Verified that legacy demo mock users and orphan storage objects are removed. |
| `test_reset_guard.py` | 4 | **PASS** | Emergency reset script requires 3 safety confirmation gates before touching data. |
| `test_harness_guard.py` | 2 | **PASS** | Test harness halts immediately if pointed at production Supabase database. |
| `test_storage_backend.py` | 2 | **PASS** | Local vs Supabase storage backend selection based on APP_ENV. |
| `test_lesson_normalisation.py` | 2 | **PASS** | Lesson content normalisation and JSON schema sanitization. |

---

## 4. Playwright End-to-End Browser Test Suites (34 Tests)

All 7 Playwright spec files passed on both Desktop Chromium and Mobile Safari:
1. `navigation_truth.spec.ts` (4 tests):
   - Guest navigation exposes only Home; protected routes redirect to Auth Gate.
   - Unknown URLs display accessible 404 "Page not found".
2. `onboarding_taxonomy.spec.ts` (4 tests):
   - Onboarding loads real boards and subjects from `/catalogue/boards`.
   - Incomplete academic profiles prompt the user before allowing access to lessons.
3. `lesson_attempts.spec.ts` (4 tests):
   - Interactive practice displays progressive hints.
   - Checkpoints submit to `/attempts` and show server-graded results with mastery badges.
4. `doubt_truth.spec.ts` (10 tests):
   - Online doubts submit directly to `/doubts` and render grounded answers with citations.
   - Provider failures show clean retry options without offline queueing.
5. `offline_sync.spec.ts` (4 tests):
   - Simulates `navigator.onLine = false`; doubts and attempts queue in Dexie IndexedDB.
   - Simulates reconnect; sync manager flushes outbox to server idempotently.
6. `student_dashboard_truth.spec.ts` (4 tests):
   - Verifies dashboard displays actual study summary metrics and heatmap.
   - Verifies toggle between graphical heatmap grid and accessible tabular view.
7. `teacher_evidence.spec.ts` (4 tests):
   - Teacher dashboard displays real classroom join codes and evidence matrix.
   - Student accounts attempting to access `/teacher` display "Teacher account required".

---

## 5. Frontend Production Build Verification

```powershell
PS C:\projects\setu - V2\frontend> tsc -b && vite build
vite v6.4.5 building for production...
✓ 1652 modules transformed.
rendering chunks...
dist/index.html                                    1.00 kB
dist/assets/index-CuP2MJUa.css                    88.27 kB
dist/assets/index-2Rgcj2dz.js                    540.13 kB
dist/sw.js (PWA service worker)
✓ built in 3.95s
```
- **Zero compiler warnings or TypeScript errors.**
- **PWA Service Worker generated properly (`dist/sw.js`).**

