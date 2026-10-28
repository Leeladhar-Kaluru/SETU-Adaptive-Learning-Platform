# SETU persistent project rules

1. The visible product name is SETU, everywhere. Never display "SETU V2", "SETU 2.0", or another version suffix in Stitch prompts, generated screens, logos, UI text, browser titles, PWA manifests, onboarding, or user-facing copy. Internal documentation may use SETU V2 when necessary.
2. No hardcoded production users, progress, subjects, languages, boards, resource counts, lessons, quizzes, classroom memberships, or fabricated analytics. Real database records and API responses only.
3. Keep production flows subject/source/board/language/student/classroom agnostic. Fixtures and deterministic fallbacks belong strictly in isolated test environments.
4. Frontend: React 19 + Vite + TypeScript + CSS Modules; no Tailwind v4 or shadcn. "The Learning Desk" design system with accessible contrast and custom CSS properties.
5. Backend: FastAPI; Supabase PostgreSQL/Auth/Storage; PostgreSQL full-text + pgvector(768).
6. Lesson packs are typed/versioned. Validate source refs, question material and visual spec before marking `ready`.
7. Background generation is durable/idempotent via PostgreSQL queue with atomic leases and worker restart recovery.
8. Offline packs, attempts, and doubts live in IndexedDB (Dexie); reconnect sync is idempotent and triggered by reconnect, focus/resume, or manual action.
9. Never output/log/commit secrets. Never expose service-role/secret keys in the browser.
10. User documents remain private; rights checked per source/asset; no NCERT rehosting without permission.
11. Clean Supabase reset: backup and inventory first, drop only application-owned tables/objects/records, preserve managed schemas (`auth`, `storage`, `vault`, `realtime`, `extensions`). Record verification in `context/RESET_REPORT.md`.
12. Use Stitch MCP for design workflows and screen generation before implementation. Compare browser output against designs.
13. Update `STATUS_REPORT.md` each session with changes, exact commands/results, tools, blockers and next steps.
