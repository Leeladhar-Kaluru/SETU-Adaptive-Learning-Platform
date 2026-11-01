---
name: setu-v2-rag
description: Use for upload, extraction, chunking, embeddings, retrieval, citations, source rights and LLM answers in SETU V2.
---

# SETU V2 RAG Skill

1. Read `05_DOCUMENT_INGESTION_AND_RAG.md`, `04_CURRICULUM_AND_RESOURCE_CATALOGUE.md` and `13_SECURITY_PRIVACY_AND_SUPABASE_RESET.md`.
2. Treat upload, extraction, chunking, embedding, indexing, retrieval and generation as separate observable stages.
3. Never mark ready before extraction/index validation. Tie every citation to immutable source version/page metadata.
4. Validate actual embedding model/dimension. Begin with Postgres FTS + pgvector.
5. Retrieve only authorised sources; reject model-created citations that don't resolve.
6. Test empty-evidence abstention and prompt injection. Uploaded content is untrusted data.
7. Run a real known-answer provider test when possible; if unavailable, report it honestly.
