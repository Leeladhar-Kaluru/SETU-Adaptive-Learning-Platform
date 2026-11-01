# SETU Reference Review & Architectural Insights

This document analyzes external educational and engineering benchmarks, patterns, and lessons relevant to SETU.

---

## 1. Educational Product Benchmarks

### 1.1 Khan Academy
- **Source / Link:** [khanacademy.org](https://www.khanacademy.org/)
- **Pedagogical Takeaway:** Clean mastery mechanics with distinct stages: Explanation -> Guided Practice -> Unit Mastery Check. Progressive hints that guide students without penalizing curiosity, and explicit prerequisite skill mapping.
- **SETU Application:** SETU's 3-stage Learn/Solve/Test structure mirrors Khan Academy's mastery philosophy, but grounds the content strictly in the student's *own uploaded or chosen curriculum document* rather than a fixed global tree.
- **Licensing / Constraints:** Proprietary content; architecture and pedagogical patterns only.

### 1.2 Brilliant
- **Source / Link:** [brilliant.org](https://brilliant.org/)
- **Pedagogical Takeaway:** Interactive, visual-first problem solving. Minimal walls of text; concepts are explained through dynamic SVG models, interactive sliders, and immediate feedback loops.
- **SETU Application:** Implementation of first-party educational SVGs (`NumberLine`, `FractionModel`, `ConceptMap`, `CoordinateGrid`, `CellMembrane`) rendered directly in the flow rather than external images or unvetted scripts.
- **Licensing / Constraints:** Proprietary; interactive visual concepts inspire SETU's deterministic SVG specs.

### 1.3 Duolingo
- **Source / Link:** [duolingo.com](https://www.duolingo.com/)
- **Pedagogical Takeaway:** Engaging onboarding and bite-sized learning pathways. Dynamic activity indicators ("Reading your document", "Finding prerequisites", "Crafting your first lessons") keep users informed during asynchronous processing without artificial delays.
- **SETU Application:** Transparent state machine transitions during ingestion, indexing, and lesson generation with realistic status messages and resumable onboarding walkthroughs.

### 1.4 DIKSHA (National Digital Infrastructure for Teachers & Students - India)
- **Source / Link:** [diksha.gov.in](https://diksha.gov.in/)
- **Pedagogical Takeaway:** Aligned to CBSE, NCERT, and State Boards across Classes 6–10 in multiple mediums (English, Hindi, etc.). Deep emphasis on QR-coded textbook chapters and teacher-led classroom evidence.
- **SETU Application:** Subject, Class, and Board neutrality in database models; preservation of exact textbook page citations (`[Page 59]`); teacher dashboards with authorised classroom membership and evidence-backed recommendations.
- **Licensing / Constraints:** NCERT / DIKSHA content remains copyright; SETU never rehosts copyrighted textbooks without rights, enforcing strict page references and student-owned document access.

### 1.5 Moodle
- **Source / Link:** [moodle.org](https://moodle.org/)
- **Pedagogical Takeaway:** Robust role-based access control (RBAC), modular course structures, gradebook aggregation, and privacy controls separating teacher views from student workspaces.
- **SETU Application:** In SETU, teacher authorization is strictly classroom-scoped via Supabase RLS and token claims. Teachers can only view evidence for students enrolled in their classes.
- **Licensing / Constraints:** GPL v3; architectural concepts for classroom grouping and assessment tracking inform SETU's classroom models.

### 1.6 Open edX
- **Source / Link:** [openedx.org](https://openedx.org/)
- **Pedagogical Takeaway:** Sequential learning units (verticals), progressive disclosure of hints, structured checkpoint quizzes, and XBlock-style composable lesson blocks.
- **SETU Application:** SETU's lesson package schema (`lesson-package.schema.json`) enforces structured Learn/Solve/Test blocks with progressive hint penalty tracking and versioned packages.
- **Licensing / Constraints:** AGPL v3; data structure schemas and progressive assessment designs inform SETU's typed JSON schema.

---

## 2. Engineering References

### 2.1 Web Interface Guidelines (Vercel Labs)
- **Source / Link:** [github.com/vercel-labs/web-interface-guidelines](https://github.com/vercel-labs/web-interface-guidelines)
- **Technical Takeaway:** Accessibility standards, focus states, responsive typography, reduced-motion preferences, dark/light contrast ratios, and elimination of generic AI boilerplate.
- **SETU Application:** Enforced via `web-design-guidelines` skill across all React 19 + CSS Modules components ("The Learning Desk" design system).

### 2.2 Dexie.js (Offline-First IndexedDB)
- **Source / Link:** [dexie.org](https://dexie.org/)
- **Technical Takeaway:** Local-first authoritative storage for offline packs, outbox queues for attempts and doubts with client-generated UUIDs, and idempotent background sync.
- **SETU Application:** Dexie stores `lessons`, `offlineVisuals`, `offlineAttempts`, `doubtOutbox`, `cachedAnswers`, and `syncEvents` with tombstone deletion and multi-tab coordination.

### 2.3 Supabase & pgvector
- **Source / Link:** [supabase.com/docs/guides/ai](https://supabase.com/docs/guides/ai)
- **Technical Takeaway:** 768-dimensional vector cosine distance search (`vector(768)`) combined with PostgreSQL Full-Text Search (`tsvector`) via Reciprocal Rank Fusion (RRF) for hybrid retrieval.
- **SETU Application:** Implemented in `retrieval.py` and Alembic migrations, verified against LM Studio's `text-embedding-nomic-embed-text-v1.5`.

### 2.4 Durable PostgreSQL Task Queue
- **Technical Takeaway:** Atomic claiming with `SELECT ... FOR UPDATE SKIP LOCKED`, lease expiry timeouts, exponential backoff, and worker restart recovery without requiring Redis or Celery.
- **SETU Application:** Implemented in `worker.py` and `jobs.py` using existing Supabase PostgreSQL instance.

