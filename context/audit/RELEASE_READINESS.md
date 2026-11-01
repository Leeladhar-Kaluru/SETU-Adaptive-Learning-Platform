# SETU — Release Readiness Assessment & Judge Demonstration Playbook

**Product Name:** SETU  
**Audit Date:** 30 October 2026  
**Auditor:** Principal Software Engineer, Staff Architect, Application Security Lead  
**Final Release Decision:** **CONDITIONAL GO**

---

> **Reconciliation — 2026-10-31.** The condition below was closed. The account
> `chotu1@gmail.com` owns **0** classrooms (the audit's ownership claim was
> false). A dedicated teacher account and classroom were created, and the
> teacher desk was verified live. The current verdict is **GO for the Round 2
> demo**, subject only to the disclosures in `STATUS_REPORT.md` section 1.4.

---

## 1. Final Verdict Justification (historical)

$$\mathbf{VERDICT:\ CONDITIONAL\ GO}$$

### Why Not a "NO-GO"?
SETU is **not** a mock, not a superficial prototype, and not broken:
- All core vertical slices—upload, extraction, OCR, 768d vector embeddings, hybrid retrieval, grounded doubt resolution with citations, learning path generation, server-side attempt grading, Bayesian mastery updating, adaptive remediation, PWA offline caching, and Dexie reconnect sync—are **fully functional and proven by 131 backend tests and 34 browser tests**.
- Zero mock data or fabricated analytics exist in the runtime codebase.

### Why "CONDITIONAL"?
The only barrier to an immediate unconditional "GO" is an operational data conflict in Supabase:
- The preserved account `chotu1@gmail.com` owns 8 classrooms but has `role = 'student'`, preventing access to the Teacher Desk under strict role enforcement.
- **The Condition:** This must be addressed prior to judging by running one SQL update or registering a dedicated teacher account.

---

## 2. Capability Readiness Matrix

| Feature / Subsystem | Readiness Status | Operational Notes for Judges |
|---|:---:|---|
| **Student Registration & Onboarding** | **READY** | Real boards, subjects, languages loaded from API. Zero hardcoded selections. |
| **Document Upload & Format Parsing** | **READY** | Supports PDF, DOCX, PPTX, TXT. Streamed progress updates to UI. |
| **OCR & Font Corruption Recovery** | **READY** | PyMuPDF Tesseract engine recovers scanned pages and dingbat-corrupted text. |
| **Vector Embeddings & Hybrid RAG** | **READY** | 768d nomic-embed-text-v1.5 + pgvector cosine similarity + full-text search. |
| **Grounded Doubt Q&A** | **READY** | Answers with page-number citations; refuses to hallucinate if ungrounded. |
| **Interactive Learn–Solve–Test** | **READY** | Reading chunks, 3-level progressive hints, timed checkpoints. |
| **Anti-Cheat Server-Side Grading** | **READY** | Answer keys redacted from client; graded securely on the backend. |
| **Bayesian Mastery & Remediation** | **READY** | Dynamically transitions bands (`developing` $\rightarrow$ `demonstrated`) and injects remediation. |
| **Student Dashboard & Heatmap** | **READY** | 100% real metrics; streak, minutes, accuracy, and 84-day interactive heatmap. |
| **PWA Offline Mode & Dexie Sync** | **READY** | Service worker precaching; doubts/attempts saved offline and synced on reconnect. |
| **Teacher Classrooms & Evidence Matrix** | **CONDITIONALLY READY** | Fully functional in code; requires a user with `role = 'teacher'`. |
| **Lesson Visual Diagrams** | **PARTIAL** | Displays `<VisualUnavailable>` notices when LLM omits visual specs. Truthful, but plain. |

---

## 3. Pre-Demo Checklist (3 Minutes)

1. **Verify Local LLM & Embedding Server (LM Studio):**
   - Ensure LM Studio is running on `http://127.0.0.1:1234`.
   - Ensure model `google/gemma-4-e4b` (or active Gemma 4 model) is loaded.
   - Ensure embedding model `text-embedding-nomic-embed-text-v1.5` is loaded.
2. **Resolve Teacher Account Role (Choose Option A or B):**
   - **Option A (Fix existing account):** In Supabase SQL Editor:
     ```sql
     UPDATE public.user_profiles
     SET role = 'teacher'
     WHERE email = 'chotu1@gmail.com';
     ```
   - **Option B (Fresh accounts):** Create `teacher@setu.org` (Role: Teacher) and `student@setu.org` (Role: Student) via the UI sign up page.
3. **Use Curated Demo Documents:**
   - Use `e2e_science.pdf` or a 5–15 page NCERT chapter for the live upload demo. Do not upload a 300-page book during a 5-minute judge pitch.

---

## 4. Step-by-Step Judge Demonstration Script

### Scene 1: Student Academic Onboarding & Truthful Empty State
1. Open `http://localhost:5173`.
2. Click **Get Started** / **Sign Up**.
3. Register a student account (e.g. `student@setu.org` with password `Password123!`).
4. Select Class 9, CBSE, Science, English.
5. **Point to highlight:** The student desk starts with clean, truthful empty states—no fabricated progress, no fake historical lessons.

### Scene 2: Textbook Upload, OCR & Outline Review
1. Drag and drop the demo PDF (`e2e_science.pdf` - Class 9 Science).
2. Observe the **Dynamic Activity Indicator**:
   - `Reading your document` $\rightarrow$ `Indexing document` $\rightarrow$ `awaiting_review`.
3. The **Review Chapter Outline** dialog opens, displaying extracted chapter headings and page ranges.
4. Click **Build Learning Path**.
5. The background worker picks up the job and begins durable generation.

### Scene 3: Grounded Doubt Answering with Page Provenance
1. Open a generated ready lesson (e.g., *The Fundamental Unit of Life*).
2. Click **Ask a Doubt** in the header or beside a reading block.
3. Type: *"What is the difference between diffusion and osmosis?"*
4. Click **Ask SETU**.
5. **Point to highlight:** The AI returns a concise, grounded explanation along with an exact clickable citation:
   > **Source:** `e2e_science.pdf`, **Page 2**  
   > *Clicking the citation opens the provenance drawer showing the exact text excerpt.*

### Scene 4: Learn–Solve–Test & Server-Side Adaptive Remediation
1. Switch to the **Solve** tab:
   - Try Question 1. Click **Need a hint?** to show Level 1 hint.
   - Submit response; server evaluates correctness without revealing answer keys upfront.
2. Switch to the **Test** tab:
   - Answer the timed checkpoint questions.
   - Intentionally fail a question to trigger the **Adaptive Remediation Engine**.
   - Observe the returned result: the system awards evidence, updates mastery band to `developing`, and enqueues a foundational remediation unit.

### Scene 5: Student Learning Consistency & Heatmap
1. Click **Student Record** / **Dashboard**.
2. **Point to highlight:**
   - Streaks, study minutes, and accuracy reflect the session just completed.
   - The 84-day heatmap shows recorded activity for today.
   - Toggle between **Grid view** and **Accessible Table view**.

### Scene 6: Teacher Desk & Evidence Matrix
1. Sign in with the teacher account (`teacher@setu.org`).
2. Navigate to **Teacher Desk** (`/teacher`).
3. Click **Create Classroom**: Name: *"Class 9A Science"*, Grade 9, CBSE, Science.
4. A unique 6-character join code is issued (e.g. `BWKN9R`).
5. Open the **Evidence Matrix**:
   - Shows enrolled students, active study minutes, and concept mastery bands.
   - Select a student needing support and submit a targeted recommendation.

---

## 5. Startup Commands for Demo Environment

Run each command in a separate PowerShell terminal:

### Terminal 1: Backend API (FastAPI)
```powershell
cd "c:\projects\setu - V2\backend"
.\.venv\Scripts\Activate.ps1
$env:PYTHONPATH="."
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

### Terminal 2: Background Queue Worker
```powershell
cd "c:\projects\setu - V2\backend"
.\.venv\Scripts\Activate.ps1
$env:PYTHONPATH="."
python -m app.worker
```

### Terminal 3: Frontend Dev Server (Vite)
```powershell
cd "c:\projects\setu - V2\frontend"
npm run dev -- --host 127.0.0.1 --port 5173
```

### Terminal 4: LM Studio (Inference Engine)
- Launch the LM Studio desktop app.
- Ensure the Local Server is running on port 1234 with CORS enabled.
- Models loaded: `google/gemma-4-e4b` and `text-embedding-nomic-embed-text-v1.5`.

