# Acceptance Tests and Evaluation Plan

## Definition of done

A pretty UI without persisted state is not done. A mocked LLM call does not prove provider connectivity. Verify each core flow with unit, service, integration, database/RLS and browser tests as appropriate.

## Upload and ingestion
1. Searchable PDF uploads, lands in private storage, produces one document record and stable status.
2. Repeated upload-finalisation calls don't duplicate record/job.
3. Known-good test PDF returns expected page count and a known phrase at a known page.
4. Scanned PDF is labelled OCR-required or processed through configured OCR; never falsely marked fully readable.
5. Oversized, unsupported and malformed input returns safe specific errors and is not ready.
6. Interrupted upload resumes/restarts without corruption or ambiguous success.
7. Storage, parser and provider errors are distinguishable.
8. Failed extraction can retry without needless duplicate work.
9. Student A cannot read/delete Student B's file or diagnostics.

## RAG and model
10. Embedder health check confirms model ID, response shape and actual vector dimension.
11. Dimension/model mismatch stops indexing with a clear developer error.
12. A labelled question retrieves its relevant source chunk within top 5 in the test corpus.
13. Answer citations resolve to exact source version/page/chunk.
14. Invented page numbers/URLs are rejected by server resolution.
15. Unanswerable question produces `insufficient_evidence`, not a fabricated source-grounded claim.
16. Model timeout/rate-limit is visible/retryable; no fake success.
17. Retrieved prompt-injection text cannot change system policy or trigger unauthorised tools.
18. Student A cannot retrieve Student B's chunks.
19. Filters that exclude all candidate chunks produce useful diagnostics, not silent empty output.
20. Retrieval/grounding metrics include test-set size and scoring method; no metric without labelled evaluation.

## Path and generated lessons
21. Path is tied to selected source version and outline.
22. Class/subject/language can be corrected before generation.
23. First 2–3 validated lessons become ready before the entire path is generated when service is healthy.
24. Later jobs retain state across page reload/worker restart.
25. Failed schema/citation/answer validation prevents `ready`.
26. Regeneration is idempotent and versioned.
27. Lessons contain objectives, source scope, explanation, worked example, practice, test, takeaways, answer/rubric, doubt anchor and safe visual spec.
28. Normal production flow does not assume Algebra or inject demo content.
29. Path completion, test score, mastery evidence and offline status are separate.

## Visuals and rights
30. Invalid renderer type/data is rejected; no model HTML/JS injection.
31. Diagram has alt text, keyboard/touch action and mobile layout.
32. External image has verified source/author/licence and permitted use; otherwise fallback or link.
33. Deletion cleans derived chunks/embeddings/assets per policy and records retryable partial failure.

## Offline and doubt sync
34. Downloaded lesson opens with network disabled and required visuals available.
35. Supported quiz works offline and saves local result.
36. Doubt added offline survives reload.
37. Reconnect/retry creates exactly one server record.
38. Answer with valid citations is stored in IndexedDB.
39. Failure leaves doubt visible with retry status.
40. Logout/account switch cannot show a previous user's private cache.
41. Quota failure never leaves a partially downloaded pack marked ready.
42. Sync works without Background Sync using online/focus/manual triggers.

## Adaptation and teacher
43. Attempts keep immutable lesson/question version and hint evidence.
44. Three labelled learner scenarios produce expected next action (prerequisite review / practice / advance / teacher help).
45. Sparse evidence displays `not enough evidence`, not confident mastery.
46. Teacher sees only explicitly authorised classroom records.
47. Every recommendation explains its evidence and can be accepted/edited/dismissed.
48. Teacher action/override persists; no hard-coded classroom ID.

## Release quality
49. Type check, production build, unit tests and backend tests pass.
50. Browser end-to-end covers upload → lesson → offline doubt → sync → answer.
51. Phone and desktop layouts, keyboard navigation and focus are verified.
52. RLS/storage policies are tested with independent users.
53. Applicable dependency/security checks are reviewed and triaged.
54. Repo scan confirms no keys, `.env` files, private dumps or unauthorised textbooks committed.
55. Session report contains exact commands/results, actual counts, failures and remaining blockers.

## Strategy

Use tests for chunking, citations, schemas, progress, mastery and idempotency; fake-provider tests for failure branches; opt-in real provider tests with current status recorded; test database data separate from personal user data; and browser e2e with offline mode. Synthetic lesson fixtures belong in tests/isolated demo mode only.
