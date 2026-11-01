# Learning Path and Lesson Pack Contract

## Goal

A learning path is an explicit, versioned plan built from a selected source and confirmed learner context. It has an ordered concept map, a small batch of ready lessons, transparent readiness/progress and source provenance.

## Course creation flow

1. Student selects a permitted catalogue resource, uploads a document, or selects a general topic where no document exists.
2. Show detected title, page count, likely language, subject clues, chapter headings and unreadable portions. The student can correct suggestions.
3. Set context: class 6–10, board if known, language/medium, goal (exam prep, chapter understanding, catch-up, revision), available time and optional prior knowledge. Minimise personal data.
4. Derive an outline and concepts with source anchors. Mark uncertain inference as such. Ask one focused review step if structure is ambiguous.
5. Build an inspectable concept/prerequisite map.
6. Optionally run a short diagnostic and explain what it measures; don't call it a diagnosis of ability.
7. Propose an ordered path and explain prerequisites.
8. Generate and validate lessons 1–3 (or fewer if source scope supports fewer).
9. Enqueue remaining lesson jobs with concurrency/cost/cancel controls.
10. Store accepted packages server-side. The student separately chooses packs for offline device storage.

## Lesson package sections

Every lesson package has stable `lesson_id`, `path_id`, `path_version`, `lesson_version`, source version IDs, grade/subject/language and translation status; estimated study time; observable objectives; prerequisite reasons; source coverage/citations; explanation blocks, vocabulary, examples and recap; visual specs with alt text/rights metadata; worked example with steps; practice questions with answer keys/rubrics; checkpoint test blueprint; graduated hints and solutions; candidate/verified misconceptions; bullet takeaways; doubt anchors for blocks/pages/questions/diagrams; estimated download size; and validation status/model/schema metadata.

A draft JSON Schema is in `schemas/lesson-package.schema.json`. It is a starting point; the agent must test it against actual model outputs and adjust consciously.

## Source grounding

- Summaries/new explanations may be generated from source, but don't reproduce substantial copyrighted passages/whole pages unless rights allow it.
- For source-derived claims, retain evidence mapping. Label supplemental general explanations separately.
- The model cannot create a citation from scratch; resolve source refs on the server.
- Use deterministic validation for supported maths/objective questions; use rubrics/review where not deterministic.
- Each external image must contain licence/attribution details. If no suitable licensed photo exists, use a diagram or omit it.

## Progress is multiple measures

Track separately:
- `lesson_status`: not_started / in_progress / completed;
- item-level `practice_attempts`;
- `test_result` plus question coverage;
- `concept_mastery_estimate` with uncertainty;
- `path_completion`: required lessons completed / total;
- `download_status`: not_downloaded / downloading / available_offline / failed / removed.

Example display: “4 of 12 lessons completed (33%). Latest checkpoint: 70%. Fractions evidence: developing (5 recent observations).” Only display numbers that derive from real records; don't collapse everything into one percentage.

## Versioning and repair

Source/language/prompt changes create new versions. Never silently alter a lesson already downloaded or attempted. Attempts link to immutable question and lesson versions. Generation failure is retryable; teachers/operators can review/reject/regenerate. Deleting source material follows a documented derivative-deletion policy and preserves a minimal source-unavailable/tombstone state where required.
