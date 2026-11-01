# SETU V2 persistent project rules

1. Read `00_START_HERE.md`, `18_MASTER_AGENT_EXECUTION_PROMPT.md` and relevant specs before coding.
2. This pack is a target specification, not evidence of current implementation; inspect the real root and services.
3. Keep production flows subject/source/board/language/student/classroom agnostic. Fixtures must be isolated from normal student views.
4. Frontend: React + Vite + TypeScript + CSS Modules; no Tailwind v4 or shadcn unless the user explicitly revises the constraint.
5. Backend: FastAPI; Supabase PostgreSQL/Auth/Storage; PostgreSQL full-text + pgvector unless measured evidence justifies change.
6. Lesson packs are typed/versioned. Validate source refs, question material and visual spec before `ready`.
7. Background generation is durable/idempotent, not a browser timer.
8. Offline packs and doubts live in IndexedDB; reconnect sync is idempotent and doesn't rely solely on Background Sync.
9. Never output/log/commit secrets. Never expose service-role/secret keys in the browser.
10. User documents private; rights checked per source/asset; no NCERT rehosting without permission.
11. Migrations are schema source of truth. Back up before destructive remote operations; preserve Supabase-managed schemas.
12. Use relevant installed skills/MCPs and report actual usage. Inspect third-party skill contents before execution.
13. Add/run tests; screenshot/mock/typecheck alone doesn't prove end-to-end success.
14. Update `STATUS_REPORT.md` each session with changes, exact commands/results, tools, blockers and next steps.
