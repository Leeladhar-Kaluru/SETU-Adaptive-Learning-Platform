# Open Decisions and Defaults

Use these defaults and proceed. Record evidence-based deviations rather than asking the user for routine approvals.

| Decision | Default | Reopen only when |
|---|---|---|
| Main root | Fresh `setu - V2`; leave old repo untouched except authorised read-only recovery inspection | User asks to port a component |
| Frontend | React + Vite + TypeScript + CSS Modules | New-root/deployment has a proven blocker |
| Styling | Custom tokens/components; no Tailwind v4 or shadcn | User changes constraint |
| Backend | FastAPI | Evidence shows a real blocker |
| Database | Existing configured Supabase PostgreSQL, clean app schema via migrations | Credentials/project configuration cannot be safely reused |
| Files | Private Supabase Storage | Proven rights/scale/cost requirements justify alternative |
| RAG | PostgreSQL FTS + pgvector | Labelled benchmark justifies more systems |
| LLM | Backend provider adapter; hosted endpoint in deployed environment; LM Studio optional for local dev | Real deployment constraints require another tested provider |
| Embeddings | Configurable model; validate real output and dimension | Model verified and chosen |
| Offline | IndexedDB via Dexie/equivalent; service worker for app shell | Device testing identifies an incompatibility |
| Generation | Durable Postgres-backed job/worker | Measured throughput justifies separate queue |
| First batch | 2–3 validated lesson packs | Source contains fewer usable sections |
| Source | Uploaded user file or approved resource; no implicit substitution | Student explicitly selects general-topic mode |
| Media | First-party SVG first; external image only with verified rights | Licensed adapter reviewed/tested |
| Classroom | Explicit teacher membership/invitation | Verified roster integration exists |
| Mastery | Explainable rules first; progress/mastery separate | Validated data supports more complex modelling |
| Language | Per-lesson language/version; only show available variants | Reviewed translation pipeline demonstrates coverage |
| OCR | Detect/mark image-only pages; OCR adapter later if needed | Demo requires it and cost/privacy are addressed |
| Supabase reset | Backup; clean SETU-owned app tables/objects; keep managed schemas | Inventory proves other user data safe to remove |

## Questions to record, not block the first slice

- Which hosted LLM and embedding provider/model is configured, and what are its cost/latency limits?
- Does SETU have written permission for public NCERT linking, and which DIKSHA/open-licence items are approved?
- Which initial document is permitted and suitable as the demo source?
- Which three languages must be reviewed in the initial demo? Keep schema support broader even if first tested coverage is small.
- Which target Android browser/device is available for offline tests?

If a secret/service is not configured, implement interfaces and deterministic tests, report the live integration as blocked, and never replace it with a fake success.
