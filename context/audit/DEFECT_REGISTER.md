# SETU — Defect & Architectural Risk Register

**Product Name:** SETU  
**Audit Date:** 30 October 2026  
**Auditor:** Principal Software Engineer, Staff Architect, Application Security Engineer  
**Scope:** Repository-wide defect inventory, root cause analysis, and remediation paths.

---

## Reconciliation — 2026-10-31

| ID | Status | Current evidence |
|---|---|---|
| DEF-01 | **Closed — invalid premise** | Live query: the student account owns **0** classrooms. The 8 legacy classrooms belong to orphan teacher ID `de898934-3c24-4d3a-baf3-53387ac557b0` (no profile row). A dedicated real teacher account and classroom were created; the full teacher flow is verified. |
| DEF-02 | **Mitigated** | `lesson_generator.py` now normalizes visual specs into renderer-shaped `{id,label}` nodes and `[from,to]` edges. When no spec exists the UI still shows the truthful fallback. |
| DEF-03 | Open | Two legacy documents still point at absent storage objects; they are not used by the demo. |
| DEF-04 | Open | Architectural transaction-coupling note; no observed failure. |
| DEF-05 | Open | Cosmetic `utcnow()` deprecation warnings. |
| DEF-06 | Open | Build now reports `567.11 kB` (`172.85 kB` gzip); still only the chunk-size advisory. |

Current release verdict after reconciliation: **GO for the Round 2 demo**, with the
disclosures recorded in `STATUS_REPORT.md` section 1.4.

---

## 1. Defect Severity Matrix (post-reconciliation)

| Severity Level | Definition | Count |
|:---:|---|:---:|
| **CRITICAL** | Blocks end-to-end user flows or demo viability; security violation or data lock. | **0** |
| **HIGH** | Major functional limitation or unhandled failure under standard conditions. | **0** |
| **MEDIUM** | Degraded user experience or partial feature omission; truthful fallback exists. | **1** |
| **LOW** | Minor friction, deprecation warning, code style, or dormant config debris. | **4** |
| **TOTAL** | | **5** |

---

## 2. Detailed Defect Inventory

---

### DEF-01: Production Account Role Inconsistency (Teacher Lockout) — CLOSED, INVALID PREMISE
- **Defect ID:** `DEF-01`
- **Status (2026-10-31):** Closed. The live database shows the account owns
  **0** classrooms, not 8. A dedicated teacher account and classroom were created
  and verified end to end.
- **Original severity:** **CRITICAL** (Demo Blocker if using `chotu1@gmail.com`)
- **Subsystem:** Authentication / Database Data Integrity
- **Affected File / DB Table:** `public.user_profiles` vs `public.classrooms`
- **Description:**
  The account `chotu1@gmail.com` (`5cee4e2f-bbdc-41f5-87c9-52cdc63e755b`) owns 8 classrooms in `public.classrooms` (`owner_teacher_id`), but its record in `public.user_profiles` has `role = 'student'`.
  When logging in with this account and visiting `/teacher`, `get_current_teacher_id` in `backend/app/core/security.py:76-81` checks `profile.role in ("teacher", "admin")`. Because it is `'student'`, it returns **HTTP 403 Forbidden**.
- **Root Cause Analysis:**
  During an earlier data cleanup phase, test accounts were purged while `chotu1@gmail.com` was preserved, but the profile role was reset to `'student'` without reassigning the ownership of the 8 existing classrooms.
- **Reproducibility:**
  1. Log in to the application using `chotu1@gmail.com`.
  2. Click on the **Teacher Desk** link in the navigation bar.
  3. Observe that the UI displays *"Teacher account required"* and all teacher API endpoints return HTTP 403.
- **Recommended Remediation:**
  Execute the following SQL update directly in the Supabase Dashboard SQL Editor:
  ```sql
  UPDATE public.user_profiles
  SET role = 'teacher'
  WHERE id = '5cee4e2f-bbdc-41f5-87c9-52cdc63e755b';
  ```
  *Alternatively for the demo:* Register a fresh teacher account via the Sign Up form and select "Teacher".

---

### DEF-02: Local LLM Rarely Generates Structured Visual Specifications
- **Defect ID:** `DEF-02`
- **Status (2026-10-31):** Mitigated. The generator now normalizes visual
  specifications into renderer-shaped `{id,label}` nodes and `[from,to]` edges;
  the truthful fallback remains when no specification exists.
- **Severity:** **MEDIUM**
- **Subsystem:** Content Generation / UI Visuals
- **Affected Files:** `backend/app/services/lesson_generator.py`, `frontend/src/components/visuals/VisualRenderer.tsx`
- **Description:**
  While the frontend has fully implemented SVG visual renderers (`ConceptMap`, `CoordinateGrid`, `FractionModel`, `NumberLine`, `CellMembrane`), the local LLM (`google/gemma-4-e4b`) frequently produces empty or unstructured visual specifications in its generated JSON. In compliance with Rule #2, the UI renders `<VisualUnavailable reason="..." />` instead of inventing fake diagrams.
- **Root Cause Analysis:**
  Smaller 4B quantized models struggle to reliably emit complex nested JSON schema blocks alongside high-quality instructional readings and practice questions.
- **Impact:**
  Lessons are conceptually rich with accurate text, hints, and quizzes, but visual diagram cards display a clean fallback placeholder notice.
- **Recommended Remediation:**
  In future iterations, run a dedicated visual generation pass with few-shot structured outputs or migrate visual extraction to extract textbook diagrams directly from the PDF via PyMuPDF's image extractor (which is already implemented in `extraction.py:188-207`).

---

### DEF-03: Orphan Storage Pointers for Two Legacy Documents
- **Defect ID:** `DEF-03`
- **Severity:** **LOW**
- **Subsystem:** Storage / Database
- **Affected DB Table:** `public.documents`
- **Description:**
  Two historical records exist in `documents` (`eval_cell.pdf` and `test/Class_9_Science_Chapter_5.pdf`) whose underlying binary files were purged from the Supabase Storage bucket `setu-documents` during an earlier cleanup session.
- **Root Cause Analysis:**
  A previous cleanup script deleted storage objects without cascading the deletion to the `documents` metadata table.
- **Impact:**
  New document uploads work flawlessly. If a user clicks to download these two specific legacy documents, the backend returns HTTP 404.
- **Recommended Remediation:**
  Purge the 2 orphaned database records or re-upload the matching PDF files to storage.

---

### DEF-04: Remediation Transaction Commit Coupling in Attempt Service
- **Defect ID:** `DEF-04`
- **Severity:** **LOW**
- **Subsystem:** Adaptive Engine / Service Architecture
- **Affected File:** `backend/app/services/attempt_service.py:300`
- **Description:**
  In `attempt_service.py`, when a student fails a checkpoint question, the engine triggers adaptive remediation:
  ```python
  if not remediation_injected:
      db.commit()
  ```
  When `remediation_injected` is `True`, the transaction commit is performed inside `generation_queue.enqueue_lesson_generation()`.
- **Root Cause Analysis:**
  `enqueue_lesson_generation` executes `db.commit()` internally, so the outer function avoided a second commit.
- **Impact:**
  The flow functions correctly, but architectural best practices dictate that the top-level service method should explicitly control the transaction lifecycle.
- **Recommended Remediation:**
  Refactor `enqueue_lesson_generation` to accept `autocommit=False` and execute an explicit single `db.commit()` at the exit of `submit_attempt`.

---

### DEF-05: Python 3.13 UTC Datetime Deprecation Warnings
- **Defect ID:** `DEF-05`
- **Severity:** **LOW**
- **Subsystem:** Backend Worker / Logging
- **Affected Files:** `backend/app/worker.py:24`, `backend/app/api/v1/teacher.py:461`
- **Description:**
  Console outputs deprecation warnings:
  ```
  DeprecationWarning: datetime.datetime.utcnow() is deprecated and scheduled for removal in a future version. Use timezone-aware objects: datetime.datetime.now(datetime.UTC).
  ```
- **Root Cause Analysis:**
  Standard Python 3.12+ deprecation of naive UTC datetimes.
- **Impact:**
  Zero functional impact; cosmetic log noise.
- **Recommended Remediation:**
  Replace `datetime.datetime.utcnow()` with `datetime.datetime.now(datetime.timezone.utc)`.

---

### DEF-06: Frontend Vite Chunk Size Warning (>500 kB)
- **Defect ID:** `DEF-06`
- **Severity:** **LOW**
- **Subsystem:** Frontend Build / Performance
- **Affected File:** `frontend/vite.config.ts`
- **Description:**
  Running `npm run build` warns:
  ```
  (!) Some chunks are larger than 500 kB after minification (dist/assets/index-2Rgcj2dz.js: 540.13 kB).
  ```
- **Root Cause Analysis:**
  Large vendor libraries (React 19, Lucide icons, Dexie) are bundled into a single entry chunk rather than code-split via dynamic imports.
- **Impact:**
  Negligible; initial load is 165 kB gzipped, well within acceptable PWA performance envelopes on 4G/5G connections.
- **Recommended Remediation:**
  Configure `build.rollupOptions.output.manualChunks` in `vite.config.ts` to separate vendor modules.

