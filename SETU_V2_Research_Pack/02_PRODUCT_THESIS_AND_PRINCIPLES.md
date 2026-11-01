# Product Thesis and Principles

## Product thesis

**SETU V2 turns a student's chosen learning material into a personal, source-grounded learning journey that keeps working when the network does not.**

The promise is not “AI can teach everything.” It is: **“Bring the material you need to learn. SETU helps you understand it, practise it, track what you know, and continue when connectivity disappears.”**

## Primary users

- **Student, Classes 6–10:** starts from an uploaded/selected source; wants clear, age-appropriate lessons and practice in a comfortable language; may have limited connectivity/device access.
- **Teacher:** needs to know which learners/concepts require attention and assign support without excessive administration.
- **Parent/guardian (later):** needs a privacy-respecting view, not surveillance or oversimplified ranking.
- **Content operator:** verifies source licences, ingestion quality, generated lessons and evaluation results.

## Product pillars

### 1. Source-first learning
The source is explicit: an uploaded file, a permitted official resource, or a chosen topic when no document is available. Show its identity, edition and processing quality. Trace source-derived claims to passage/page references; label supplemental explanations.

### 2. Learn → Solve → Test
- **Learn:** small-step concept explanation, concrete examples, source references, appropriate diagram and check-for-understanding.
- **Solve:** guided practice, graduated hints, worked solution and misconception-specific feedback.
- **Test:** independent check with varied question types. Keep test evidence distinct from completion.

### 3. Progressive readiness
Generate the first two or three validated lesson packs early. The remainder shows `Queued`, `Generating`, `Validating`, `Ready`, `Failed—retry`, or `Review needed`. Never make empty lesson cards look ready. Source/language changes create versioned content, not silent replacement of a downloaded lesson.

### 4. Offline as a real capability
Students can explicitly download lesson packs, read, take supported quizzes, add notes/doubts, and see synced answers offline. Show the exact sync/download state. Do not imply new LLM generation works offline.

### 5. Teacher stays central
The model explains and recommends. Teachers can see evidence, provide context, assign work, override and dismiss suggestions. Say which skill needs support; never assign a stigmatic identity such as “weak student.”

### 6. Indian context without false coverage
The schema supports boards, year, class, subject, medium and language. Content coverage is based on verified resource records, not a board dropdown. Translation status is explicit: original, reviewed translation, AI draft (not reviewed), unavailable.

## Why this is more than a document chatbot

- Source catalogue and rights metadata.
- Concept dependency map rather than just a summary.
- Structured lesson packs: explanations, examples, visuals, practice, quiz, takeaways and doubt anchors.
- Learner evidence that changes the next step.
- Offline packs and queued interactions.
- Teacher evidence and interventions.
- RAG/lesson/answer validation before content is ready.

## Anti-patterns to reject

- Algebra, student, class, language, resource or classroom IDs hard-coded in production paths.
- Completion percent computed from cards opened, not lessons completed.
- LLM answer shown as grounded without retrieval evidence.
- Upload marked successful although extraction/indexing failed.
- Offline-ready flag without a fully persisted pack.
- Unbounded generation without quotas, cancel/retry and validation.
- Web images without source, author/licence and alt text.
- Rehosting textbooks because they are publicly downloadable.
- “Translated” label when lesson content is still in a different language.
- Generic dashboard cards, fake activity, arbitrary charts and buttons that do nothing.
