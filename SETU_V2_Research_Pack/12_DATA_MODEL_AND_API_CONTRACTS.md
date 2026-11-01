# Data Model and API Contracts (Proposed)

This is a target model, not an instruction to create every table in one migration. Implement the smallest coherent slice, preserve foreign keys, and expand through forward-only migrations.

## Main entities

### Curriculum/resources
- `curriculum_boards(id, code, name, region, official_url, active)`
- `subjects(id, code, canonical_name, ...)`; `languages(id, bcp47_tag, native_name, script, ...)`
- `resource_sources(id, name, source_type, source_url, terms_url, last_verified_at, verification_status)`
- `resources(id, source_id, title, board_id, academic_year, grade, subject_id, language_id, publisher, edition, resource_kind, external_url, verification_status)`
- `resource_rights(resource_id, license_name, license_url, rights_notes, can_link, can_download, can_store, can_process, can_embed, can_offline_cache, can_redistribute, reviewed_at, reviewer)`
- `resource_versions(id, resource_id, edition, checksum, published_at, observed_at, status)`

### Documents/retrieval
- `documents(id, owner_id, source_mode, resource_version_id nullable, original_filename, storage_bucket, storage_key, mime_type, size_bytes, sha256, language_id, grade, subject_id, status, created_at, deleted_at)`
- `document_pages(id, document_version_id, page_number, extracted_text, extraction_quality, parser_metadata)`
- `document_chunks(id, document_version_id, page_start, page_end, heading_path, chunk_index, text, text_hash, language_id, access_scope, embedding_model_id, embedding_dimension, embedding vector(...), search_text/tsvector, created_at)`
- `ingestion_jobs(id, document_id, status, stage, progress_metadata, attempt_count, error_code, timestamps, idempotency_key)`

Only choose the vector dimension after the configured embedding model has been probed and confirmed. Store model/version/dimension metadata; never mix incompatible embedding spaces silently.

### Learning
- `concepts(id, concept_key, title, subject_id, grade_range, language_id, source_scope, review_status)`
- `concept_prerequisites(concept_id, prerequisite_concept_id, relation_type, rationale, confidence, source_ref)`
- `learning_paths(id, owner_id, document_id/resource_version_id, path_version, grade, subject_id, language_id, goal, status, outline_json, created_at)`
- `path_lessons(id, path_id, lesson_key, sequence, status, current_lesson_version_id)`
- `lesson_versions(id, path_lesson_id, version_number, lesson_package_json, source_version_ids, validation_status, estimated_bytes, generation_metadata, created_at)`
- `questions(id, lesson_version_id, question_key, type, prompt_json, answer_key_json, rubric_json, concepts, validation_status)`
- `quiz_attempts(id, owner_id, question_id, question_version, response_json, grading_method, score, hint_level, feedback_json, occurred_at, sync_idempotency_key)`
- `concept_evidence(id, owner_id, concept_id, source_attempt_id, evidence_type, outcome, weight, rationale, occurred_at)`
- `concept_mastery_snapshots(id, owner_id, concept_id, estimate_band, numeric_estimate nullable, evidence_count, freshness, explanation_json, calculated_at, model_version)`
- `student_notes(id, owner_id, lesson_version_id, block_id, note_text, created_at, updated_at)`

### Doubts/sync
- `doubts(id, owner_id, client_doubt_id, path_id, lesson_version_id, block_id, source_page, question_text, attachment_refs, status, answer_json, source_refs, created_at, submitted_at, answered_at, last_error_code)`
- Unique constraint on `(owner_id, client_doubt_id)`.
- `sync_events(id, owner_id, client_event_id, event_type, payload_version, received_at, applied_at, result_json)` with uniqueness on `(owner_id, client_event_id)` where appropriate.

### Teacher
- `classrooms(id, owner_teacher_id, name, board_id, grade, subject_scope, created_at)`
- `classroom_memberships(id, classroom_id, student_id, role, status, added_by, created_at)`
- `teacher_actions(id, teacher_id, student_id/classroom_id, action_type, reason_json, status, created_at, resolved_at)`
- `teacher_notes(id, teacher_id, student_id, concept_id nullable, note_text, created_at)` with strict access policy.

### Generation jobs
`generation_jobs(id, job_type, owner_id, path_id, path_version, lesson_id, priority, status, attempt_count, max_attempts, not_before, lease_owner, lease_expires_at, idempotency_key, input_hash, output_hash, error_code, safe_error_message, cost_metadata, created_at, started_at, completed_at)`.
Use a unique idempotency key scoped to the action/source/version.

## Relationship rules

- A document belongs to one owner or explicit shared scope with permission metadata.
- Every chunk belongs to an immutable document/resource version.
- Lesson packages reference source versions and server-resolved citation IDs, not arbitrary model-provided URLs.
- Attempts link to the immutable lesson/question version actually shown.
- Client IDs are not authentication; server derives ownership from the current session.
- Teacher must be current authorised classroom member to access learner records.

## Illustrative API shape

- `POST /api/v1/documents/upload-intents` — reserve authorised upload.
- `POST /api/v1/documents/{id}/complete-upload` — verify object and enqueue ingestion idempotently.
- `GET /api/v1/documents/{id}` — status and safe extraction summary.
- `GET /api/v1/documents/{id}/diagnostics` — authorised diagnostics only.
- `POST /api/v1/documents/{id}/outline` — request/retrieve candidate outline.
- `POST /api/v1/learning-paths` — create draft from confirmed scope/goal.
- `POST /api/v1/learning-paths/{id}/approve` — confirm plan and enqueue first batch/rest.
- `GET /api/v1/learning-paths/{id}` — current path and job summary.
- `GET /api/v1/learning-paths/{id}/lessons/{lessonKey}` — owner's lesson package.
- `POST /api/v1/attempts` — idempotent attempt/evidence submission.
- `POST /api/v1/doubts` and `GET /api/v1/doubts` — outbox sync, status, answer.
- `POST /api/v1/sync/batch` — bounded idempotent offline events.
- `GET /api/v1/resources` — verified catalogue records and allowed actions.
- Teacher routes must verify current classroom membership on every request.

## API conventions

Use typed results rather than ambiguous HTTP 200 with `{}`. Include stable error code, safe message and `retryable`. Keep job state separate from content result. Bound pagination. Return signed URLs only after an access check and with short expiry. Don't return full document content by default.
