# SETU V2 — Research & Build Pack

**Prepared:** 28 October 2026. **Purpose:** A fresh product and engineering brief for the SETU V2 rebuild. This describes a target, not an already-working application.

> Start with `00_START_HERE.md`, then use `18_MASTER_AGENT_EXECUTION_PROMPT.md` as the coding agent's primary instruction.

## Product in one sentence

SETU helps a student learn from a source they select or upload, creates a curriculum-aware path with a few ready lessons first, adapts Learn/Solve/Test to demonstrated understanding, remains useful offline through saved lesson packs and a synchronised doubt queue, and keeps the teacher central.

## Contents

- `00_START_HERE.md` — key product decisions.
- `01_PROBLEM_STATEMENT_TRACEABILITY.md` — requirements mapped to the attached challenge PDF.
- `02_PRODUCT_THESIS_AND_PRINCIPLES.md` — product direction and anti-patterns.
- `03_USER_JOURNEYS_AND_FUNCTIONAL_REQUIREMENTS.md` — student, teacher and operator workflows.
- `04_CURRICULUM_AND_RESOURCE_CATALOGUE.md` — curriculum and source-library design.
- `05_DOCUMENT_INGESTION_AND_RAG.md` — upload, extraction, embeddings, retrieval, citations and diagnostics.
- `06_LEARNING_PATH_AND_LESSON_PACKS.md` — generated lesson package contract.
- `07_BACKGROUND_GENERATION_JOBS.md` — durable lesson generation.
- `08_OFFLINE_FIRST_AND_DOUBT_SYNC.md` — PWA, IndexedDB, offline queue and sync.
- `09_ADAPTIVE_LEARNING_ENGINE.md` — mastery evidence and next-step policy.
- `10_VISUAL_ENGINE_AND_IMAGE_RIGHTS.md` — deterministic visuals and media licensing.
- `11_TARGET_ARCHITECTURE.md` — system boundaries and stack.
- `12_DATA_MODEL_AND_API_CONTRACTS.md` — proposed entities/APIs.
- `13_SECURITY_PRIVACY_AND_SUPABASE_RESET.md` — privacy, RLS, secrets and reset plan.
- `14_DESIGN_SYSTEM_AND_UI_DIRECTION.md` — intentional design principles.
- `15_SCREEN_INVENTORY.md` — screen and state inventory.
- `16_ACCEPTANCE_TESTS_AND_EVALUATION.md` — quality gates.
- `17_EXECUTION_ROADMAP.md` — implementation sequence.
- `18_MASTER_AGENT_EXECUTION_PROMPT.md` — paste/use this with the coding agent.
- `19_RESEARCH_SOURCES_AND_CONFIDENCE.md` — source register and caveats.
- `20_AGENT_SKILLS_AND_MCP_PLAYBOOK.md` — how to use agent skills and MCPs properly.
- `21_OPEN_DECISIONS_AND_DEFAULTS.md` — defaults to avoid repeated approvals.
- `schemas/` — JSON schemas and a synthetic-only lesson fixture.
- `catalogue/resource-source-catalog.json` — verified source portals and conservative rights defaults.
- `.agents/skills/*/SKILL.md` — SETU-specific skills; active agent support must be checked.
- `source-materials/` — supplied Code Kernel problem statement.
- `reference-images/` — four concept boards and contact sheet.

## Important boundaries

- UI boards are **generated concept references**, not screenshots of an existing product, official textbook illustrations, approved final UI, or proof that a feature exists. Sample text/numbers/book covers may be inaccurate.
- This pack does not claim every board, textbook, subject, language or official resource is available. Catalogue only verified items with source and rights metadata.
- NCERT's official notice restricts republication, redistribution, rehosting and use inside digital content packages/software; links may require written permission. Do not bundle NCERT PDFs into SETU or offline lesson packs without appropriate written rights. See the source log.
- DIKSHA rights vary by item; verify each item. Don't assume the whole catalogue is universally reusable.
- The user requested clean SETU V2 app data in the current Supabase project. Back up first; reset only the intended SETU-owned scope and never drop Supabase-managed schemas. This pack contains no API keys.
- Preserve secrets. `.env` values must never be printed in reports, logs, screenshots, generated documents or Git.
- No Tailwind v4 or shadcn. Prefer React + Vite + TypeScript + CSS Modules.

## Current truth

Everything here is target design or researched source notes, not evidence about the old/new codebase. The agent must inspect the new root and record verified results in `STATUS_REPORT.md` at the end of every session.
