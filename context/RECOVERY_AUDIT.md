# SETU Comprehensive Recovery Audit & Defect Matrix

**Audit Date:** 2026-10-28  
**Scope:** Full codebase audit, Supabase cleanup verification, pipeline and security repairs.  
**Product Name:** **SETU**

---

## 1. Primary Failure Matrix

| Failure | Reproduction | Root cause | Fix | Verification |
|---|---|---|---|---|
| Upload fails or is invisible | Uploading 10MB+ file in UI | `upload_document` waited for synchronous extraction & embeddings; frontend never called `GET /documents` | Return `stored` immediately; extraction runs on background worker; frontend polls `/documents` | `test_upload_returns_before_extraction` PASSED |
| Corrupted PDF text embedded | Extracting PDF with corrupted font mappings (e.g. `✙❡♠` symbols) | `is_scanned = (char_count < 40)` passed corrupted pages with 1000+ symbol chars as "high" quality | Implemented `_is_corrupted_text` printable ASCII/Indian-script ratio & dingbat density gate; flagged as `low`/`needs_ocr` | `test_corrupted_symbol_font_detection` PASSED |
| Progress remains at 40% / stuck | Worker crashed or restarted during long extraction | Document stayed locked with no lease timeout | Added `lease_owner`, `lease_expires_at`, and `attempt_count` on `documents`; atomic recovery | `test_worker_job_claiming_and_lease_expiry` PASSED |
| Learning plan never appears | Path creation after upload | Frontend passed `documentId`, backend expected `document_id`; chapters were dropped | Added alias `documentId`; chapters parsed from extracted headings & page ranges | `test_create_path_accepts_document_id_alias`, `test_outline_uses_document_headings` PASSED |
| Online doubt is queued | Submitting question while online | `LessonReaderPage` routed all non-200 responses and format errors to IndexedDB outbox; `DoubtQueuePage` only fetched local DB | Route online doubts directly to API; only queue on genuine network disconnect (`TypeError` / `!navigator.onLine`); merged server doubts in `DoubtQueuePage` | `test_idempotent_doubt_sync` & `test_full_e2e_vertical_slice` PASSED |
| Old users / storage objects remain | Inspect Supabase Auth & Storage | Legacy users and orphaned files from earlier test iterations | Controlled cleanup: removed all 9 Auth users, 4 Storage objects, and application rows; schema preserved | `context/SUPABASE_CLEANUP_MANIFEST.md` verified 0 legacy rows |
| Mock / fake content appears | Lesson reader fallback & hardcoded fallbacks | `getDefaultDemoPackage` and `_build_deterministic_lesson_package` with hardcoded plasma-membrane text | Removed demo fallbacks from frontend; gated deterministic generator strictly as test fixture; dynamic `validatedAt` | `test_lesson_reader_has_no_demo_package` PASSED |
| Auth bypass / hardcoded UUID | Unauthenticated requests | `security.py` defaulted unauthenticated student/teacher requests to hardcoded UUIDs | Removed hardcoded UUID fallbacks; return 401 when unauthenticated | 22/22 pytest suite verified with authenticated sessions |
| FTS retrieval database crash | Search query in hybrid retrieval | `retrieval.py` queried `c.search_text` which did not exist on `document_chunks` | Alembic migration `005` added `search_text tsvector GENERATED ALWAYS` and GIN index; parameterized vector query | `005_add_search_text_to_chunks.py` applied, hybrid retrieval PASSED |
| Identical chunks for every lesson | Worker lesson generation | Worker queried `DocumentChunk.document_id == path.document_id` with `limit(5)` ignoring chapter | Filtered chunks by chapter `pageStart`/`pageEnd` range from outline | Verified page-range chunk retrieval in `worker.py` |

---

## 2. Additional Verified Repairs

1. **Auth Double-UUID Bug**: Fixed `auth.py` where UUID was regenerated after token creation. Replaced silent fake-token generation with truthful HTTP 503 during external auth unavailability.
2. **Dynamic Validation Timestamps**: `validatedAt` in `LessonGeneratorService` now uses `datetime.datetime.now(datetime.timezone.utc).isoformat()` rather than a hardcoded static string.
3. **Token Budget & Timeout**: Increased local model generation token budget to 6,000 tokens and HTTP client timeout to 120s in `AIProviderService` for reliable local Gemma 4 lesson generation.
4. **Citation Rendering**: Fixed hardcoded citation strings in `LessonReaderPage.tsx` drawer so real excerpts from any subject/book are displayed with exact page numbers.
5. **Multi-Document Support**: Enhanced `HomePage.tsx` with document switcher tabs when multiple learning materials are uploaded.


## 1. Upload freezes and the file never appears

**Cause.** `POST /api/v1/documents/upload` in `backend/app/api/v1/documents.py` reads the file, writes it to Storage, then extracts text and embeds every chunk inside the same request. The handler returns only after that pipeline finishes.

**Evidence.** `process_document_pipeline` is awaited before the JSON response. Embedding calls use a 30 second timeout each. The desk sets progress to 30, then waits on `fetch`, which does not report byte progress (`frontend/src/pages/HomePage.tsx`, `frontend/src/services/api.ts`).

**Impact.** An 18 MB file can sit on screen around that fixed 30 percent while Storage already has the object. If the browser gives up, the row exists and the interface never receives `documentId`. Refresh does not help: `GET /documents` exists, and the desk never calls it.

**Fix.** Return as soon as the private object and the `stored` row are confirmed. A worker claims the row, extracts, and embeds. The desk lists `GET /documents` and shows byte progress only during the browser upload.

## 2. Storage failures were ignored, and failed embeddings became zero vectors

**Cause.** A Storage exception was printed and processing continued. An embedding exception was replaced with a 768-length zero vector, then the document was marked `ready`.

**Impact.** The interface could claim a document was indexed when the bucket write failed, or when the embedding model was down.

**Fix.** A failed bucket write sets `failed` and returns that error. Embedding errors fail the document with a short message. No zero-vector substitute.

## 3. Learning paths ignored the uploaded document

**Cause.** The desk sends `documentId`. `CreatePathRequest` only read `document_id`, so the id was dropped. With no chapters, the handler inserted "Core Foundational Principles" and generated lesson 1 inside the HTTP request. Later lessons waited on `python -m app.worker`.

**Impact.** Approving an upload did not ground the path in that file. The first request could freeze again on lesson generation.

**Fix.** Accept `documentId`. Require `awaiting_review` or `ready` and real pages. Build chapters from extracted headings and page ranges. Enqueue every lesson, with the first three at higher priority.

## 4. The lesson screen showed a fake Class 9 package

**Cause.** `LessonReaderPage` called `getDefaultDemoPackage` whenever the lesson request failed. That package is a plasma-membrane lesson with citations to pages 59 and 60 of "Class 9 Science Textbook".

**Impact.** Any missing or unfinished lesson looked like a finished science chapter.

**Fix.** Remove that fallback. Show a not-ready state and poll until a stored package exists.

## 5. Teachers received a prefilled classroom

**Cause.** `GET /teacher/classrooms` inserted "Class 9 Science - Batch A" with join code `SETU-9A-SCI` when the teacher had no rows.

**Impact.** An empty account looked populated. The recommendation form also started with a cell-membrane note.

**Fix.** Return an empty list. The teacher desk shows the create-classroom form. Recommendation fields start empty.

## 6. Online doubts were saved as offline

**Cause.** If the doubt response was anything other than `status === "answered"` with `answerJson`, or if the request threw, the reader wrote the doubt into IndexedDB. `lessonVersionId` was sent as `"1"`, which is not a UUID, so `POST /doubts` could reject the body before the model ran.

**Impact.** A student who was online saw a queued-offline message, including for model errors.

**Fix.** Queue only when the browser is offline or the request fails before a response. Show model errors as retryable failures. Ignore non-UUID lesson version ids.

## 7. One navigation for both roles

**Cause.** `App.tsx` and `Navigation.tsx` always showed Desk, Offline Library, Doubt Queue, and Teacher Desk.

**Fix.** Students and signed-out visitors see the learning desk. Teachers see the teacher desk. `/teacher` does not mount the classroom API unless the profile role is teacher.

## Files

- `backend/app/api/v1/documents.py`
- `backend/app/api/v1/learning_paths.py`
- `backend/app/api/v1/teacher.py`
- `backend/app/api/v1/doubts.py`
- `backend/app/worker.py`
- `backend/app/services/lesson_generator.py`
- `backend/app/models/jobs.py` (lesson jobs still require a path and a lesson, so document work uses lease columns on `documents` instead)
- `frontend/src/pages/HomePage.tsx`
- `frontend/src/pages/LessonReaderPage.tsx`
- `frontend/src/pages/TeacherDashboardPage.tsx`
- `frontend/src/App.tsx`
- `frontend/src/components/Navigation.tsx`
