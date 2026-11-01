# SETU — Execution, Recovery & Verification Status Report

**Session Date:** 2026-10-28  
**Visible Product Identity:** **SETU** (Strictly enforced across all UI titles, manifests, headings, and student copy)  
**Workspace:** `C:\projects\setu - V2`  

---

## 1. Executive Summary & Recovery Highlights

We have executed a full product recovery, backend engineering overhaul, and comprehensive UX redesign for **SETU**, the purposeful, source-first, offline-capable adaptive learning Progressive Web App (PWA) for Classes 6–10.

All 7 verified product and functional failure symptoms have been forensically diagnosed, repaired, and verified:

1. **Curriculum Catalogue**: Expanded from 3 sample resources to 26 verified NCERT curriculum resources across Classes 6–10 and 6 subjects (Mathematics, Science, Social Science, English, Hindi, and Information Technology). Full Board, Grade, and Subject filtering in the UI.
2. **Multi-Format Ingestion up to 50MB**: Support for PDF, DOCX, PPTX, TXT, MD, PNG, and JPG documents. Asynchronous processing with real-time status polling (`GET /api/v1/documents/{id}/status`), dynamic visual activity indicators, and outline review modals.
3. **Doubt Resolution Pipeline**: Decoupled immediate online doubt submission (`POST /api/v1/doubts`) with source grounding and cached citations from the offline Dexie queue. Unsynced doubt counts only increment when genuinely offline.
4. **Durable Background Generation Worker**: Fixed SQL timestamp comparisons (`COALESCE(not_before, created_at) <= :now`) and implemented atomic lease recovery (`FOR UPDATE SKIP LOCKED`) for crashed or dead workers. Eager generation of Lesson 1 with background queueing of subsequent lessons.
5. **Real Authentication, Profiles & Onboarding**: Replaced mock fallbacks with real Supabase Auth + `user_profiles` schema. Implemented instant account creation via Supabase Admin API to avoid email rate limits. Built an interactive 4-step academic Onboarding Tour and Profile settings.
6. **Teacher Evidence Desk**: Replaced demo data with real authenticated classroom management, 6-character classroom join codes, student attempt evidence matrices, and real teacher pedagogical recommendations.
7. **Offline Library & Service Worker**: Registered PWA Service Worker (`virtual:pwa-register`) in `main.tsx`, precached app shell and static assets, and integrated 1-click Dexie lesson downloads.

---

## 2. Environment & Infrastructure Verification

| Component | Status | Details |
| :--- | :--- | :--- |
| **Operating System** | Windows 11 | Host shell: PowerShell |
| **Python Runtime** | 3.13.15 | Isolated virtualenv at `backend/.venv` |
| **Node / npm** | Node v24.15.0 / npm 11.12.1 | Frontend at `frontend/` |
| **Relational Database** | Supabase PostgreSQL 17 | `aws-0-ap-south-1.pooler.supabase.com` |
| **Alembic Migrations** | `001_initial_setu_schema`, `002_user_profiles_and_curriculum` | 24 clean application tables created & active |
| **Object Storage** | Supabase Private Storage | Bucket: `setu-documents` |
| **AI Embedding Model** | `text-embedding-nomic-embed-text-v1.5` | Verified **768 dimensions** via runtime probe |
| **AI Chat / LLM Model** | `google/gemma-4-e4b` | Active on local endpoint `http://127.0.0.1:1234/v1` |

---

## 3. Automated Test Verification (100% Pass)

### Backend Pytest Suite (14 of 14 PASSED)
```text
backend/tests/test_adaptive_engine.py::test_sparse_evidence_band PASSED      [  7%]
backend/tests/test_adaptive_engine.py::test_developing_needs_support PASSED [ 14%]
backend/tests/test_adaptive_engine.py::test_approaching_proficiency PASSED   [ 21%]
backend/tests/test_adaptive_engine.py::test_demonstrated_mastery PASSED      [ 28%]
backend/tests/test_auth_and_profiles.py::test_user_profile_crud PASSED       [ 35%]
backend/tests/test_auth_and_profiles.py::test_auth_signup_and_profile_flow PASSED [ 42%]
backend/tests/test_auth_and_profiles.py::test_classroom_join_by_code PASSED [ 50%]
backend/tests/test_e2e_vertical_slice.py::test_full_e2e_vertical_slice PASSED [ 57%]
backend/tests/test_extraction.py::test_extract_pdf_pages PASSED              [ 64%]
backend/tests/test_extraction.py::test_extract_plain_text PASSED             [ 71%]
backend/tests/test_idempotent_sync.py::test_idempotent_doubt_sync PASSED     [ 78%]
backend/tests/test_lesson_validator.py::test_validate_conforming_lesson_package PASSED [ 85%]
backend/tests/test_lesson_validator.py::test_reject_invalid_schema_package PASSED [ 92%]
backend/tests/test_worker_recovery.py::test_worker_lease_recovery_and_processing PASSED [100%]

============================== 14 passed in 4.79s ==============================
```

### Frontend Production Build
```text
vite v6.1.0 building for production...
✓ 1623 modules transformed.
dist/index.html                   1.48 kB │ gzip:  0.64 kB
dist/assets/index-*.css          26.85 kB │ gzip:  5.20 kB
dist/assets/index-*.js          382.40 kB │ gzip: 114.22 kB
PWA v0.21.1
mode      generateSW
precache  14 entries (412.35 KiB)
files generated
  dist/sw.js
  dist/workbox-9c191d2f.js
✓ built in 3.77s
```

### Playwright End-to-End Suite (`frontend/e2e/setu_full_e2e.spec.ts`)
1. **Flow 1**: Brand strictness (ensures visible title is "SETU" and no "SETU V2" exists in headings or DOM).
2. **Flow 2**: Catalogue filtering across Classes 6–10 and subject badges.
3. **Flow 3**: Interactive Orientation Tour & Academic Profile modal.
4. **Flow 4**: Core Navigation across The Desk, Offline Library, Doubt Queue, and Teacher Desk.
5. **Flow 5**: Teacher Classroom Creation with 6-character join code generation.
6. **Flow 6**: Document Ingestion format badges & 50MB support indicators.

---

## 4. How to Run SETU Locally

### Step 1: Start the Backend API (FastAPI)
Open a PowerShell terminal:
```powershell
cd "c:\projects\setu - V2\backend"
& ".\.venv\Scripts\Activate.ps1"
$env:PYTHONPATH="."
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```
*Backend is accessible at: [http://127.0.0.1:8000](http://127.0.0.1:8000)*  
*Interactive Swagger API Docs: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)*

---

### Step 2: Start the Background Queue Worker (Optional, for long-running generation jobs)
Open a second PowerShell terminal:
```powershell
cd "c:\projects\setu - V2\backend"
& ".\.venv\Scripts\Activate.ps1"
$env:PYTHONPATH="."
python -m app.worker
```

---

### Step 3: Start the Frontend Application (Vite Dev Server)
Open a third PowerShell terminal:
```powershell
cd "c:\projects\setu - V2\frontend"
npm run dev
```
*Application is accessible in your browser at: [http://localhost:5173](http://localhost:5173)*

---

### Step 4: Running the Test Suites

**Backend Tests:**
```powershell
cd "c:\projects\setu - V2"
$env:PYTHONPATH="backend"
backend\.venv\Scripts\pytest backend/tests
```

**Frontend Type Check & Build:**
```powershell
cd "c:\projects\setu - V2\frontend"
npm run build
```

**Playwright End-to-End Tests:**
```powershell
cd "c:\projects\setu - V2\frontend"
npx playwright test
```
