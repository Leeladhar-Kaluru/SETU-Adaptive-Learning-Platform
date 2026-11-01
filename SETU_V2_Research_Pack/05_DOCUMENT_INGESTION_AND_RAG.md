# Document Ingestion and RAG Specification

## Goal

A student asks about a selected source and receives an answer grounded in the exact accessible document/version, with page or section references. If extraction or retrieval is insufficient, SETU explains the limitation rather than returning a generic model answer disguised as source-grounded.

## Pipeline and states

`created → uploading → stored → queued_for_extraction → extracting → extracted → chunking → chunked → embedding → indexed → ready`

Failure states: `upload_failed`, `unsupported_type`, `too_large`, `extraction_failed`, `scanned_pdf_ocr_required`, `empty_text`, `embedding_failed`, `index_write_failed`, `permission_failed`, `cancelled`.

Never mark `ready` on upload completion alone. Persist timestamps, attempt count, `error_code`, safe `error_message` and a correlation/job ID. Logs must not include document bodies, signed URLs or API secrets.

## Supported inputs and practical scope

Prioritise searchable PDF, DOCX, PPTX, plain TXT/Markdown where safe, and individual JPG/PNG pages as a separate path. Detect image-only/scanned PDFs. OCR is a distinct capability with cost/privacy implications; if disabled, report exactly what could not be read and ask for a searchable file. Never claim OCR-free extraction understood image pages.

Configure allowlists and limits centrally: allowed extension and actual file signature/MIME, bytes, page count, extraction time, decompressed size and per-user quotas. Do not trust the filename/browser MIME alone. Generate internal storage keys.

## Secure upload

1. Authenticate/authorise before issuing an upload intent.
2. Validate file type/signature server-side; enforce size/runtime limits.
3. Use a private bucket and generated object key.
4. Supabase recommends TUS/resumable uploads for larger files (its docs cite >6 MB as a use case) and unstable networks; configure the actual project limits.
5. Confirm storage only after verifying the object.
6. Enqueue ingestion after metadata is persisted; finalisation is idempotent.
7. Originals remain private. Serve short-lived signed URLs only after an access check.

## Extraction and provenance

- Every page/chunk/lesson citation binds to an immutable `document_version_id`.
- Extract by page, preserve page number, headings, section path, table metadata and bounding boxes where feasible.
- Store quality signals: text length/page, empty pages, replacement-character rate, ordering warnings, scanned detection, table/image presence and parser warnings.
- Do not flatten the whole book into one untraceable string. Preserve page/section anchors and parser version.
- Keep source bytes in Storage. Page crops/derived images are optional, private and deleted according to source deletion policy. Preserve slide numbers in PPTX and heading/paragraph/table references in DOCX where practical.

## Chunking

Split around chapter/section headings, paragraphs, lists, numbered steps, tables and equations where possible. Page boundaries are citation metadata, not an absolute split rule. Every chunk stores document/version, owner/access scope, page range, heading path, language, subject/board/year, hash, chunk index, extractor version, embedding model ID and dimension. An initial experiment around 350–700 tokens with modest overlap is a starting hypothesis, not a universal law; tune using labelled retrieval tests and language/document variation.

## Embeddings and search

- Store the real embedding model ID/version and output dimension. Reject mismatches before insertion; never mix incompatible embedding spaces silently.
- Begin with Postgres full-text search plus pgvector in the same Supabase database. Combine rankings only if evaluation shows benefit.
- Apply permission and source filters within retrieval before evidence reaches the model.
- Search the selected source by default; cross-library search must be explicit and authorised.
- Exact nearest neighbour is a reasonable first baseline for a modest corpus. Enable HNSW after benchmarking. pgvector notes approximate-index filtering may reduce matching results; test recall under filters.
- Do not add a second vector database by default.

## Grounded question-answer contract

1. Authenticate and resolve allowed source IDs.
2. Classify request: `source_question`, `explain_concept`, `quiz_or_grade`, `generate_lesson`, `general_chat`, `unsupported`.
3. For source questions, retrieve authorised evidence and include title, page/section, excerpt and source version in context.
4. If evidence is empty/weak, return `insufficient_evidence` with a useful recovery action.
5. Call a configured backend provider through a clear interface. Treat uploaded/retrieved content as untrusted data, never as instructions that can alter policy or tools.
6. Validate output schema and resolve citations on the server. Reject invented page numbers/URLs.
7. Save source chunk IDs, provider/model version, schema/prompt version, status, timing and citations without unnecessary sensitive logs.
8. Return answer, citations, limitations and retryable error states. Never say “based on your document” when no relevant evidence was retrieved.

## Model endpoint reality

Use a backend abstraction for embeddings and chat. Support an OpenAI-compatible hosted endpoint and optional LM Studio locally. No private API from the browser. If configured URL is `127.0.0.1`, it means the machine running that backend process; a deployed worker cannot automatically access the developer's laptop. Test provider/model ID, response schema, timeout and health at startup.

## Developer diagnostics

An authorised diagnostics route/command should show file/extraction status, pages and empty pages, extracted character count, chunk count, average token size, embedding model/dimension/vector count, index readiness, sample retrieved scores and provenance for an owned test file, provider status and safe error category. Never show diagnostics for another student's file.

## Minimum labelled RAG evaluation

Build a fixed test corpus with questions and relevant pages. Evaluate recall@5, citation correctness, answer faithfulness, relevance/grade-level clarity, abstention behaviour, parser/embedding/model failure reporting and cross-user isolation. Metrics such as context precision/recall, faithfulness and answer relevance are useful tools, not magic numbers; set thresholds using the actual labelled dataset.
