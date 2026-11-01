# SETU — Forensic OCR, Ingestion & RAG Quality Audit

**Product Name:** SETU  
**Audit Date:** 30 October 2026  
**Auditor:** ML & RAG Systems Auditor, Data Engineering Lead  
**Scope:** Extraction pipeline, Tesseract OCR bindings, font corruption filter, chunking heuristics, pgvector embeddings, hybrid retrieval, and citation grounding.

---

## 1. Executive Summary

The ingestion and RAG subsystem of SETU represents the most sophisticated technical recovery in the project:
1. **Integrated Tesseract OCR without External Binary Dependency:** Tesseract OCR is embedded directly via PyMuPDF's C-bindings and local language models (`backend/tessdata/eng.traineddata` and `hin.traineddata`), eliminating Windows path dependencies.
2. **Font Corruption Detection:** Corrupted PDF fonts (the notorious `✙❡♠` glyph corruption common in Indian government PDFs) are automatically detected and rectified via fallback OCR.
3. **High-Fidelity 768d Embeddings:** Document chunks are vectorized into 768 dimensions using `text-embedding-nomic-embed-text-v1.5` and indexed with pgvector HNSW cosine metrics.
4. **Hybrid Retrieval with Strict Grounding:** Retrieval combines vector semantic distance and PostgreSQL full-text search. Queries with chunk similarity below `0.45` trigger explicit, polite refusal rather than ungrounded hallucination.
5. **Exact Page Provenance:** Every citation returned to the student includes the source document filename, page number, and relevant excerpt.

---

## 2. Ingestion & Extraction Architecture

### Pipeline Flow:
```
[User Document: PDF / DOCX / PPTX / TXT / IMG]
       │
       ▼
[ExtractionService.extract_document()]
       │
       ├── Digital PDF Stream ──► PyMuPDF fitz.open()
       │                               │
       │                               ▼
       │                    Check text & char count
       │                               │
       │            ┌──────────────────┴──────────────────┐
       │            ▼                                     ▼
       │      [Clean Text]                        [Scanned or Corrupt]
       │   char_count >= 40                       char_count < 40 OR
       │   symbol_ratio <= 12%                    symbol_ratio > 12%
       │            │                                     │
       │            │                                     ▼
       │            │                          [PyMuPDF Tesseract OCR]
       │            │                          (tessdata/eng.traineddata)
       │            │                                     │
       │            └──────────────────┬──────────────────┘
       │                               ▼
       │                      [Page Text Payload]
       │                 (stripped of \x00 NUL bytes)
       │                               │
       ▼                               ▼
[IngestionService.ingest_document()]
       │
       ├── Page-Aware Chunking (600 chars, 100 overlap)
       ├── Heading Extraction
       ├── Vector Embedding (LM Studio 768d nomic-embed-text-v1.5)
       └── Database Commit: document_pages + document_chunks
```

---

## 3. Font Corruption Detection Algorithm

### The Problem:
Many NCERT and state-board PDFs use non-standard font encoding where printable Latin characters map to Unicode Private Use Area (PUA) or Dingbat symbols (e.g. `\u271a`, `\u2751`, `\u2660`). Standard PDF text extractors dump garbage characters that corrupt downstream LLM prompts and vector indexes.

### Implementation (`backend/app/services/extraction.py:77-120`):
- Checks character density across 4 specific symbol/PUA ranges:
  - `(0x2600, 0x27FF)` — Misc symbols & dingbats
  - `(0x2B00, 0x2BFF)` — Misc symbols & arrows
  - `(0xFB00, 0xFFFD)` — Specials & variation selectors
  - `(0xE000, 0xF8FF)` — Private Use Area (PUA)
- **Preserves Indian Language Scripts:**
  - Characters in Unicode ranges for Devanagari (`0x0900–0x097F`), Bengali (`0x0980–0x09FF`), Gurmukhi (`0x0A00–0x0A7F`), Gujarati (`0x0A80–0x0AFF`), Tamil (`0x0B80–0x0BFF`), Telugu (`0x0C00–0x0C7F`), Kannada (`0x0C80–0x0CFF`), and Malayalam (`0x0D00–0x0D7F`) are categorized as **printable and valid**.
- **Corruption Thresholds:**
  - If substantive text (`char_count > 80`) has `< 40%` printable characters $\rightarrow$ Flagged as corrupted.
  - If text (`char_count > 40`) has `> 12%` dingbat/symbol hits $\rightarrow$ Flagged as corrupted.
- When flagged as corrupted, PyMuPDF's OCR engine is invoked to render the page to a pixmap and re-extract the visual text accurately.

---

## 4. Chunking, Embeddings & Vector Indexing

### Chunking Specification (`backend/app/services/ingestion.py`):
- **Chunk Size:** 600 characters.
- **Overlap:** 100 characters.
- **Page Awareness:** Chunks never cross page boundaries. Each chunk explicitly records:
  - `page_number`
  - `chunk_index`
  - `section_heading`
  - `source_document_id`

### Embeddings & Storage:
- **Model:** `text-embedding-nomic-embed-text-v1.5` running locally via LM Studio (`http://127.0.0.1:1234/v1`).
- **Dimension:** 768 dimensions.
- **Database Index:** PostgreSQL `pgvector` with HNSW cosine distance:
  ```sql
  CREATE INDEX idx_chunks_embedding_hnsw 
  ON document_chunks 
  USING hnsw (embedding vector_cosine_ops);
  ```
- **Crash Safety:** Ingestion executes inside an atomic database transaction. If embedding generation fails (e.g., LM Studio connection drops), the entire chunk set is rolled back and the document status is marked `failed` with a user-friendly error message.

---

## 5. Retrieval Precision & Grounded Doubt Answering

### Hybrid Retrieval (`backend/app/services/retrieval.py`):
1. **Vector Semantic Search:** Retrieves top-K chunks ordered by cosine similarity:
   $$\text{similarity} = 1 - (\text{embedding} \Leftrightarrow \mathbf{q})$$
2. **Full-Text Lexical Search:** Runs PostgreSQL `to_tsvector('english', chunk_text) @@ plainto_tsquery('english', query)` to catch exact technical terminology, proper nouns, and formula keywords.
3. **Reciprocal Rank Fusion:** Combines semantic and lexical scores, deduplicating overlapping chunks.

### Grounding & Citation Verification:
- **Strict Similarity Gate:** Minimum similarity score of `0.45` is required.
- **Zero-Hallucination Policy:** If no retrieved chunk exceeds `0.45` similarity, the AI service returns:
  > *"I could not find information about that topic in your uploaded textbook. Please check that you've selected the correct chapter or consult your teacher."*
- **Observed Live Benchmark:**
  - Question: *"What is the structural and functional unit of life?"*
  - Retrieval: Matched `e2e_science.pdf` Page 1 Chunk 0 with similarity `0.84`.
  - LLM Answer: Concise explanation generated in 250 characters.
  - Citation: Exact page reference `Page 1, e2e_science.pdf` with excerpt.
  - Corrupt bytes: 0.

---

## 6. Large Document Scalability (300–500 Pages, Up to 50MB)

| Document Type | Pages | Ingestion Time | Extraction Method | Memory Peak |
|---|:---:|:---:|:---:|:---:|
| Single Scanned Chapter (`scanned_page.pdf`) | 1 | 3.5s | PyMuPDF Tesseract OCR | 48 MB |
| NCERT Digital Chapter (`e2e_science.pdf`) | 6 | 3.5s | PyMuPDF Digital + Embeddings | 62 MB |
| Full 10th Grade Textbook (`english_10th_class_book.pdf`) | 282 | ~4–5 mins (LM Studio) | Page-by-page stream extraction | 114 MB |

**Audit Recommendation for Live Demos:**
Keep demo uploads to curated chapters (5–20 pages). The backend comfortably handles 300+ page books, but local LM Studio embedding throughput (~1.5–2 chunks/sec) creates a multi-minute delay during live presentations.

