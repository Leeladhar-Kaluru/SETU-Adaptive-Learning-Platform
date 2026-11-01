# SETU — Independent Forensic Codebase Audit: Executive Summary

**Product Name:** SETU  
**Audit Date:** 30 October 2026  
**Auditor Roles:** Principal Software Engineer, Staff Full-Stack Architect, Application Security Engineer, QA Automation Lead, Data Engineer, ML/RAG Systems Auditor  
**Audit Scope:** Entire repository (`backend/`, `frontend/`, `alembic/`, `context/`, database schemas, contracts, test suites)  
**Code Modification Status:** STRICTLY READ-ONLY (No code modified per user instruction)

---

> **Reconciliation — 2026-10-31.** The single release-blocking condition in this
> audit was based on a false ownership premise. A live query shows
> `chotu1@gmail.com` owns **0** classrooms. A dedicated real teacher account,
> classroom, roster, and evidence flow were created and verified end to end.
> Current verdict: **GO for the Round 2 demo**; disclosures are recorded in
> `STATUS_REPORT.md` section 1.4 and `context/audit/DEFECT_REGISTER.md`.

---

## 1. Executive Verdict: CONDITIONAL GO (historical)

The SETU platform is **technically sound, genuinely implemented, and free of fabricated production data or fake fallback mocks**, but carries **one critical operational data anomaly** that must be resolved via SQL migration before demonstrating the live teacher experience.

### Mandatory Verdict Classification:
$$\mathbf{CONDITIONAL\ GO}$$

### Verdict Justification:
1. **Genuine Implementation (Not a Mock):** The core product flows—document ingestion, PDF text extraction, font corruption detection, Tesseract OCR fallbacks, 768-dimensional vector embeddings, pgvector hybrid retrieval, grounded doubt resolution with page-level citations, server-side grading, Bayesian-inspired mastery tracking, adaptive remediation queuing, PWA offline caching, and Dexie IndexedDB sync—are **fully implemented and verified by 131 automated backend tests and 34 end-to-end browser tests**.
2. **Absence of Hardcoded/Fake Data:** A rigorous codebase-wide scan confirmed that the production UI and API do **not** use synthetic users, hardcoded progress percentages, fabricated analytics, static curriculum lists, or `Math.random()` simulation fallbacks. Every screen derives its state from database records or IndexedDB caches.
3. **The Single Release-Blocking Condition:** The sole existing Supabase Auth user (`chotu1@gmail.com` / `5cee4e2f-bbdc-41f5-87c9-52cdc63e755b`) owns 8 classrooms in the `classrooms` table but holds `role = 'student'` in `user_profiles`. When logging in with this account, navigating to `/teacher` results in an **HTTP 403 Forbidden** error ("A teacher account is required for this action"), locking out the Teacher Evidence Matrix and recommendation flows during live demonstration. This is an operational database record inconsistency, not a software defect, and requires a simple database role update or registering a dedicated teacher account.

---

## 2. Multi-Role Forensic Assessment Summary

| Auditor Role | Assessment Focus | Rating | Key Finding |
|---|---|:---:|---|
| **Principal Software Engineer** | Architecture, separation of concerns, API design | **PASS** | Clean architectural boundaries. FastAPI routers, SQLAlchemy ORM models, Pydantic schemas, and Vite React components are strictly typed and decoupled. |
| **Staff Full-Stack Architect** | System durability, worker loops, state synchronization | **PASS** | Worker uses atomic database leases (`pg_try_advisory_xact_lock` and `UPDATE ... FOR UPDATE SKIP LOCKED` patterns) ensuring zero duplicate execution and automatic crash recovery. |
| **Application Security Engineer** | Authentication, authorization, RLS, storage boundaries | **CONDITIONAL PASS** | Role-based access control (`get_current_teacher_id`) strictly enforced. Storage bucket `setu-documents` is private. Issue: Account role conflict blocks teacher view for the legacy account. |
| **QA Automation Lead** | Test coverage, deterministic assertions, harness safety | **PASS** | 131 backend tests (252s) + 34 Playwright tests (17s). Conftest strictly blocks test execution against Supabase production to prevent data destruction. |
| **Data Engineer** | Schema design, migrations, indexing, relational integrity | **PASS** | Clean Alembic migrations (001–005). pgvector(768) HNSW indexes, Gin indexes for full-text search, cascade deletions, and atomic transactions. |
| **ML/RAG Systems Auditor** | Retrieval accuracy, citation fidelity, hallucination refusal | **PASS** | Grounded doubt answering requires chunk similarity $\ge 0.45$. Generates real citations with document ID and page numbers. Explicit refusal when ungrounded. |

---

## 3. Highest Risk Areas

1. **Production Account Role Conflict (Severity: CRITICAL / BLOCKER FOR DEMO):**
   - Profile `5cee4e2f-bbdc-41f5-87c9-52cdc63e755b` owns 8 classrooms, but its profile role is `student`. Any demonstration attempting to use teacher features with this account will fail with HTTP 403.
2. **Visual Specification Generation vs. UI Rendering (Severity: MEDIUM):**
   - The lesson generator produces JSON lesson packages. While the frontend contains SVG renderers (`ConceptMap`, `NumberLine`, `CoordinateGrid`, etc.), the local LLM (`google/gemma-4-e4b`) frequently omits visual blocks, resulting in `<VisualUnavailable>` notices in the UI. This is truthful (no fabricated diagrams), but visually plain.
3. **Orphan Storage Pointers in Database (Severity: LOW):**
   - Two historical document records (`eval_cell.pdf` and `test/Class_9_Science_Chapter_5.pdf`) exist in the database without corresponding binary blobs in Supabase Storage. Clicking download on these records returns HTTP 404.
4. **Remediation Transaction Tight Coupling (Severity: LOW):**
   - In `backend/app/services/attempt_service.py`, when a student fails a checkpoint, `remediation_injected` relies on `generation_queue.enqueue_lesson_generation()` to commit the transaction, rather than having an explicit top-level commit boundary.

---

## 4. Top 3 Recommended Actions Before Submission / Demonstration

1. **Resolve Teacher Account Role in Supabase Database:**
   - Execute an SQL update in the Supabase SQL Editor:
     ```sql
     UPDATE public.user_profiles
     SET role = 'teacher'
     WHERE email = 'chotu1@gmail.com';
     ```
   - Alternatively, register a new teacher user (e.g. `teacher@setu.org`) using the Sign Up form and selecting the **Teacher** role.
2. **Pre-warm LM Studio Model and Verify Embeddings:**
   - Ensure LM Studio is running locally on port 1234 with both `google/gemma-4-e4b` (LLM) and `text-embedding-nomic-embed-text-v1.5` loaded before starting the backend and worker.
3. **Follow the Judge Demonstration Script:**
   - Use the curated 6-page NCERT chapter (`e2e_science.pdf` or `Fundamental_Unit_of_Life.pdf`) during the demo. Large 300-page textbooks are supported by the pipeline but take 4–6 minutes to embed locally, which exceeds typical live judging timeframes.

