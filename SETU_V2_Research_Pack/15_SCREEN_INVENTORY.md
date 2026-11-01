# Screen Inventory

This is an inventory of meaningful screens and states, not a mandate to create many empty routes. Build them as the underlying workflows become real; related states can share responsive pages.

## Student / core
1. Welcome/source-first start — Upload, Browse Resources or Continue.
2. Resource Library — verified filters: board/year/class/subject/language/type/action.
3. Resource Details / Rights — source, edition, language, permitted actions, verification date.
4. Upload Document — file picker/drop, limits, progress and retry/resume state.
5. Processing Status — extraction stages, quality summary, OCR-needed pages and retry.
6. Source Outline Review — sections/page ranges and inclusion controls.
7. Learner Context — grade/board/subject/language/goal; inferred fields editable.
8. Diagnostic Check — optional small baseline.
9. Learning Path Proposal — ordered concepts, prerequisites and rationale.
10. My Learning Path — ready/generating/queued/failed lessons and genuine progress.
11. Lesson Reader — explanation blocks, citations, visuals, takeaways and doubts.
12. Visual Focus — accessible interactive diagram, reset and static fallback.
13. Guided Practice — attempt, hints, feedback and worked-solution disclosure.
14. Test / Checkpoint — independent assessment and result state.
15. Results & Next Step — scores, evidence coverage, estimate and recommendation.
16. Doubt Composer — text, passage/page/question/visual context, optional attachment.
17. Doubt Queue — offline, sending, processing, answered and failed/retry states.
18. Doubt Answer — answer with valid source citation and offline-saved state.
19. Offline Library / Downloads — packs, estimated size, remove and failure state.
20. Sync Center — pending/success/failure events and manual Sync.
21. Notes & Saved Items — local note plus sync state.
22. Settings / Language / Storage — available languages, quota, downloads, private-data clearing.

## Teacher / classroom
23. Teacher Overview — real, persisted classroom metrics.
24. Class Roster / Membership — explicit invite/add/remove and permissions.
25. Concept Evidence Map — learner × concept, not-enough-evidence separated from support-needed.
26. Student Learning Timeline — attempts/hints/tests, role-gated.
27. Recommended Interventions — reason/evidence/limitations, accept/edit/dismiss.
28. Assignment Builder — choose validated lessons/practice and assign to authorised members.
29. Teacher Notes / Follow-up — private notes and actions.

## Operator / quality (role-gated)
30. Source Catalogue Manager — URLs, licences and action permissions.
31. Ingestion Job Monitor — stage/status/errors/retry, no unnecessary raw source text.
32. Generation Queue Monitor — status, retry, provider health and costs where available.
33. RAG Evaluation Run — labelled questions, retrieval/citation/faithfulness reports.
34. Model/Dependency Health — provider/model IDs and health status, never key values.
35. Audit/Deletion Status — privacy-safe audit trail and partial deletion recovery.

## Cross-cutting states

First-use empty, loading, success, validation failure, offline, backend/provider unavailable, permission denied, missing/stale version, weak extraction, downloaded/not downloaded, retry/recovery, responsive/keyboard/screen-reader states.

## First design deliverable

Create an interaction map and wireframes for the P0 vertical slice; implement it. Don't create 35 static screens before data contracts, error states and interactions are real.
