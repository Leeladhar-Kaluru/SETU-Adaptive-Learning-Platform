# User Journeys and Functional Requirements

## A. Start from a student document

1. Student chooses `Upload a document` or `Choose an official/approved resource`.
2. Upload gives type/size limits, progress, resume/retry where supported and precise errors.
3. Backend validates and stores privately; processing extracts page/section anchors and reports scanned/image-only pages.
4. Student reviews suggested title, class, subject, language and goal; inferred metadata is editable.
5. SETU displays a detected outline, weak-extraction areas and the scope used to generate material. Student can exclude irrelevant sections.
6. Optional diagnostic checks establish a baseline without becoming an unexplained barrier.
7. SETU proposes a path and reasoned prerequisite order; student confirms.
8. First 2–3 lesson packages become ready only after validation. Other lessons are enqueued and show truthful status.

## B. Study a lesson

Every lesson includes the source/book/section, page citations and `open source` action where permitted; measurable objectives; short explanation blocks; a concrete example; purposeful visuals; takeaways/vocabulary; checks for understanding; contextual `Ask a doubt`; and a real `Save offline` state. A language switch is available only when that lesson language exists; otherwise show truthful availability.

## C. Solve, test and adapt

1. Student attempts before seeing the full answer.
2. Hints reveal progressively and are recorded as evidence, not automatically counted as failure.
3. Use deterministic grading for supported numeric/objective questions, rubric-based grading for open responses, and LLM assistance only where appropriate.
4. Feedback links to the concept and supporting source when possible.
5. Checkpoint test measures independent understanding.
6. Result separates lesson completion, test performance and concept mastery estimate.
7. Explain the next action—review prerequisite, practise, move ahead, take a checkpoint or ask teacher—and allow reasonable choice.

## D. Offline and doubt queue

- Student explicitly downloads a lesson pack and required permitted visual assets.
- Saved lesson/quiz opens without network.
- A doubt may be tied to a lesson block, source page, question or diagram. Save it to IndexedDB immediately with a stable client ID.
- Show `Waiting to sync`; retain through reload/restart.
- When online, app resumes/focuses or user taps Sync, send with an idempotency key.
- Distinguish `Queued offline`, `Sending`, `Processing`, `Answered`, `Needs retry`, `Needs sign-in`.
- Cache a completed answer plus citation metadata locally before marking answered.
- Do not remove an item when an API/model call fails. Background Sync is a bonus, never the only trigger.

## E. Teacher supports the class

- Classroom membership is explicit and permission checked; no automatic demo class assignment.
- Class view shows concept evidence/coverage and distinguishes `not enough evidence` from `needs support`.
- Each recommendation shows why, evidence, limitations and a useful next task.
- Teacher can accept/edit/dismiss a recommendation and assign a validated lesson/practice set.
- Notes and learner records remain permission-bound.

## P0 requirements

Resource select/upload, validation, extraction report, private document record; indexed page-aware chunks; RAG answer with citations and insufficient-evidence response; source-grounded path; 2–3 fully validated lesson packs; Learn/Solve/Test; durable background job; offline download and doubt outbox; idempotent reconnect sync; truthful progress/states; tests and a browser walk-through.

## P1 and later

P1: richer curriculum adapters, more diagram renderers, teacher membership/dashboard, reviewed translation pipeline, licenced media API and deeper analytics. Later: parent views, voice/live sessions, broad board mappings, advanced mastery models and large-scale authoring CMS.

## Non-functional

Mobile-responsive, keyboard accessible, low-bandwidth mindful, private by default, useful errors/loading/empty/offline/retry states, authorised API, RLS and a real browser test for each key journey.
