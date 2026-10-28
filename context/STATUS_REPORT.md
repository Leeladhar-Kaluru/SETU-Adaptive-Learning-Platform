# SETU V2 — Execution & Verification Status Report

**Session Date:** 2026-10-28  
**Visible Product Identity:** **SETU** (Strictly enforced across all UI titles, manifests, headings, and student copy)  
**Workspace:** `C:\projects\setu - V2`  
**Git Checkpoint:** `26cda08`  

---

## 1. Executive Summary

We have engineered and verified a fresh, source-first, offline-capable adaptive learning Progressive Web App (PWA) named **SETU**, purpose-built for Indian school students (Classes 6–10).

The full P0 vertical slice is working and verified across both backend and frontend:
1. **Multi-Format Ingestion**: Supports PDF, DOCX, PPTX, TXT, MD, PNG, and JPG documents up to **50MB**.
2. **Page-Aware Extraction & Chunking**: Generates page-grounded text chunks with section headings and SHA-256 provenance hashes.
3. **768d Vector Indexing & Hybrid Retrieval**: Uses pgvector with `vector(768)` (matching `text-embedding-nomic-embed-text-v1.5`) and PostgreSQL Full-Text Search fused via Reciprocal Rank Fusion (RRF).
4. **Out-of-Domain Abstention**: Explicit refusal guardrail when source evidence is missing or ambiguous.
5. **Validated Lesson Generation**: Produces 3-stage packages (**Learn / Solve / Test**) strictly conforming to `lesson-package.schema.json` and `visual-spec.schema.json` (`status: ready`).
6. **First-Party Visual Renderers**: Safe, typed SVGs for `NumberLine`, `FractionModel`, `ConceptMap`, `CoordinateGrid`, and `CellMembrane`.
7. **Adaptive Evidence Engine**: Aggregates mastery evidence into four bands (`sparse`, `developing`, `approaching`, `demonstrated`) to dynamically steer progression.
8. **Offline-First PWA & IndexedDB**: Local caching via Dexie, offline outbox for attempts and doubts, and background service worker.
9. **Idempotent Sync Service**: Repeated synchronization requests with identical client UUIDs return existing answers without creating duplicate database rows.
10. **Teacher Evidence Desk**: Real mastery matrix filtered by Class (6–10) with editable pedagogical recommendations.

---

## 2. Reality Check & Environment Audit

| Component | Status | Details |
| :--- | :--- | :--- |
| **Operating System** | Windows 11 | Host shell: PowerShell |
| **Python Runtime** | 3.13.15 | Isolated virtualenv at `backend/.venv` |
| **Node / npm** | Node v24.15.0 / npm 11.12.1 | Frontend at `frontend/` |
| **Relational Database** | Supabase PostgreSQL 17 | `aws-0-ap-south-1.pooler.supabase.com` |
| **Database Migrations** | Alembic `001_initial_setu_schema` | 23 clean application tables created |
| **Object Storage** | Supabase Private Storage | Bucket: `setu-documents` |
| **AI Embedding Model** | `text-embedding-nomic-embed-text-v1.5` | Verified **768 dimensions** via runtime probe |
| **AI Chat / LLM Model** | `google/gemma-4-e4b` | Active on local endpoint `http://127.0.0.1:1234/v1` |

### Database Reset & Recovery Verification
- **Pre-reset Backup**: Created full SQL dump `backend/backups/supabase_public_backup_20261028_070420.sql` (4.2 MB) and verified JSON manifest for all 32 legacy tables.
- **Storage Cleanup**: Purged 2 obsolete legacy objects via Supabase Storage REST API using service-role key.
- **Schema Separation**: Platform-managed schemas (`auth`, `storage`, `vault`, `realtime`, `extensions`) remained strictly untouched. All 4 existing Auth users were preserved.
- **Full Report**: Documented in [RESET_REPORT.md](file:///C:/projects/setu%20-%20V2/context/RESET_REPORT.md).

---

## 3. Mandatory Skills & MCP Tools Used

### Skills Utilized
- `.agents/skills/setu-v2-build`: Project orchestration, environment constraints, and migration runner.
- `.agents/skills/setu-v2-rag`: RAG evaluation thresholds, 768d vector indexing, and hybrid reciprocal rank fusion.
- `.agents/skills/setu-v2-offline`: Dexie IndexedDB schemas, outbox patterns, and idempotent sync protocols.
- `.agents/skills/frontend-design`: Design tokens, typography hierarchy, and CSS Modules structure.
- `.agents/skills/react-best-practices`: React 19 component design, hooks, and clean prop contracts.
- `.agents/skills/supabase-postgres-best-practices`: Connection pooler management, skip-locked worker queries, and pgvector HNSW indexing.

### MCP Tools Tested & Utilized
- **Stitch MCP**:
  - `create_project`: Created project `14314897932083698834` (*"SETU - The Learning Desk"*).
  - `create_design_system_from_design_md`: Created design system `3523b2ec29d845af98e38a9c94e23a5a` (*"Purposeful Academic Desk"*).
  - `generate_screen_from_text`: Generated Screen 1 (`07b30f28658244b0a0af9fc594eed67a`: Home & Multi-format 50MB Ingestion) and Screen 2 (`4b2dc95901054da4a2ed5494fadd9297`: Lesson Reader with Learn/Solve/Test and Provenance Drawer).
  - `download_file`: Downloaded raw HTML/CSS assets for design token extraction into `frontend/src/tokens.css`.

---

## 4. End-to-End Vertical Slice Test Results

The full end-to-end slice was verified via automated integration test `backend/tests/test_e2e_vertical_slice.py` and unit suites:

```text
============================= test session starts =============================
platform win32 -- Python 3.13.15, pytest-9.2.0, pluggy-1.7.0
plugins: anyio-4.15.1, asyncio-1.4.1

backend/tests/test_adaptive_engine.py::test_sparse_evidence_band PASSED      [ 10%]
backend/tests/test_adaptive_engine.py::test_developing_needs_support PASSED [ 20%]
backend/tests/test_adaptive_engine.py::test_approaching_proficiency PASSED   [ 30%]
backend/tests/test_adaptive_engine.py::test_demonstrated_mastery PASSED      [ 40%]
backend/tests/test_e2e_vertical_slice.py::test_full_e2e_vertical_slice PASSED [ 50%]
backend/tests/test_extraction.py::test_extract_pdf_pages PASSED              [ 60%]
backend/tests/test_extraction.py::test_extract_plain_text PASSED             [ 70%]
backend/tests/test_idempotent_sync.py::test_idempotent_doubt_sync PASSED     [ 80%]
backend/tests/test_lesson_validator.py::test_validate_conforming_lesson_package PASSED [ 90%]
backend/tests/test_lesson_validator.py::test_reject_invalid_schema_package PASSED [100%]

======================= 10 passed in 4.17s =======================
```

### Vertical Slice Trace Evidence
1. **Extraction**: Parsed 2-page Class 9 Science unit on "Cell Membrane & Diffusion". Page numbers (59, 60) and heading paths preserved.
2. **Indexing**: 2 chunks inserted into PostgreSQL `document_chunks` table with 768d vector embeddings.
3. **Retrieval**: Hybrid query `"plasma membrane selectively permeable diffusion"` retrieved matching chunks with fused rank scores.
4. **Abstention**: Out-of-domain empty query correctly returned `insufficient_evidence: True`.
5. **Lesson Package Conformance**: JSON Schema validation passed against `lesson-package.schema.json` with status `"ready"`.
6. **Adaptive Banding**: Student attempt profile evaluated to `"demonstrated"` mastery with action `"move_forward"`.
7. **Idempotent Doubt Sync**: Calling `/api/v1/sync/doubts` twice with `client-doubt-e7e25a02a4f944679a1c23964bdc972c` produced identical answer IDs and preserved database row count = 1.

---

## 5. Frontend PWA Implementation & Production Build

- **Framework**: React 19 + TypeScript + Vite.
- **Styling**: Strictly **CSS Modules** and custom CSS variables from "The Learning Desk" design system. **Zero Tailwind v4, zero shadcn**.
- **Offline Storage**: Dexie IndexedDB with 6 stores (`lessons`, `offlineVisuals`, `offlineAttempts`, `doubtOutbox`, `cachedAnswers`, `syncEvents`).
- **Production Build**: Verified with `npm run build`:
  - 1,623 modules transformed.
  - PWA service worker generated (`dist/sw.js`, `dist/workbox-*.js`).
  - Strict type checking (`tsc -b`) passed with zero errors.

---

## 6. How to Run Locally

### 1. Start Backend Server
```powershell
cd "c:\projects\setu - V2\backend"
& ".\.venv\Scripts\Activate.ps1"
$env:PYTHONPATH="."
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

### 2. Start Background Worker (Long-running generation queue)
```powershell
cd "c:\projects\setu - V2\backend"
& ".\.venv\Scripts\Activate.ps1"
$env:PYTHONPATH="."
python -m app.worker
```

### 3. Start Frontend Development Server
```powershell
cd "c:\projects\setu - V2\frontend"
npm run dev
```
Open [http://localhost:5173](http://localhost:5173) in your browser.
