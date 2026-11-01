# Execution Roadmap

The full target is broader than one hackathon slice. As of 28 October, the challenge PDF states Build 25–29 October and Prove 30–31 October 2026. Focus on a credible end-to-end proof while keeping the architecture multi-subject; don't claim total India-wide curriculum coverage.

## Phase 0 — clean-root preflight

- Use the new `setu - V2` folder; leave old repo untouched except an authorised read-only recovery inspection.
- Read the complete pack and supplied PDF.
- Inspect environment variable names and configured endpoints with secrets redacted.
- Discover real skills/MCP tools; inspect/use relevant ones.
- Set up Git; ensure secrets/data ignored.
- Inventory current Supabase schema/migrations/buckets/objects and make/verify a backup before resetting the intended SETU-owned scope. Never drop managed schemas.
- Record actual provider models and constraints.

**Exit gate:** correct root/project/services confirmed; no changes made against a guessed target.

## Phase 1 — foundations/contracts

Scaffold React/Vite/TS/CSS Modules and FastAPI; typed config/health checks; migrations for source/document/job/lesson; authentication, private storage and RLS. Start with honest empty states and no fake class/demo feed.

**Exit gate:** repeatable migrations, builds, auth and private upload permission tested.

## Phase 2 — upload/RAG vertical slice

Upload one controlled test PDF; extract per page; chunk; embed; confirm dimension and DB writes; hybrid retrieve; resolve citation; test known/unknown questions. Add developer diagnostics before RAG enters the polished UI.

**Exit gate:** complete RAG chain is testable and failure stages are distinct.

## Phase 3 — path + first 2–3 lesson packs

Create outline/concept map with edit step; generate validated first lesson packs; build one or two useful SVG diagram renderers; Learn/Solve/Test and attempts; durable worker for remaining lessons.

**Exit gate:** reload preserves content; job retry/restart works; citations and applicable answer keys validate.

## Phase 4 — offline PWA/doubt queue

App-shell caching, IndexedDB schema, explicit lesson downloads, offline quizzes and doubt outbox; idempotent API sync on reconnect/focus/manual request; test real offline browser behaviour.

**Exit gate:** offline-to-online e2e passes.

## Phase 5 — adaptation and teacher value

Evidence events, transparent next-step rules, explicit classroom membership, teacher view and editable recommendations.

**Exit gate:** labelled learner scenarios route correctly; privacy membership tests pass.

## Phase 6 — breadth and polish

More verified curriculum sources and language versions; broader renderers; accessibility/responsive review; browser regression, storage/performance budgets; rights review; full acceptance suite.

## Immediate demo route

1. Upload or select a permitted test source.
2. Show real extraction/indexing status.
3. Review outline/path.
4. First three lessons show real citations, a useful visual and takeaways.
5. Student answers and next step changes for a reason.
6. Save lesson offline and add doubt offline.
7. Reconnect; doubt syncs once; answer and citation are cacheable offline.
8. Teacher view can see the evidence and suggest support.

One verified source can demonstrate the architecture. It must not imply full national coverage. The data model and code path remain generic across subject/language metadata.
