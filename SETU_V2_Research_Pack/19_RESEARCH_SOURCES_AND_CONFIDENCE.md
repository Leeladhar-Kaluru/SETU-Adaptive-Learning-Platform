# Research Sources and Confidence Notes

**Checked:** 28 October 2026. Source pages, product APIs and academic-year content can change; reopen primary sources before implementing critical behaviour.

## A. Challenge source

### Code Kernel '26 — Adaptive Learning for Classes 6 to 10
- Included in `source-materials/Code-Kernel-26-Problem-Statement-Decode.pdf`.
- Pages 1–4 cover the pacing problem, Indian context, teacher role, Learn/Solve/Test, desired qualities and event schedule.
- High confidence for the supplied PDF's text. The stated schedule is what that PDF says; recheck organiser updates if deadline-critical.

## B. Official education content

### NCERT online textbooks
- [Official selector](https://ncert.nic.in/textbook.php)
- [ePathshala selector](https://epathshala.nic.in/wp-content/doc/book/btextbook/textbook.htm)
- Evidence: the selector describes classes I–XII in Hindi, English and Urdu, with chapter and full-book downloads.
- **Key limit:** NCERT's notice says textbooks are copyrighted; republication, redistribution, rehosting and use inside digital-content packages/software are prohibited and links may require written permission.
- Confidence high for the notice's text; seek permission/legal review for how it applies to SETU's exact integration.
- [Direct Class X Science prelims PDF](https://www.ncert.nic.in/textbook/pdf/jesc1ps.pdf) is a single introductory/prelims file, not a full textbook.
- [Older Class 8 Mathematics selector example](https://ncert.nic.in/textbook.php?hemh1=0-16); verify edition before any use.

### Telangana SCERT
- [Official site](https://www.scert.telangana.gov.in/) and [alternate official domain](https://scert.telangana.gov.in/).
- [Indexed E-Books listing](https://www.scert.telangana.gov.in/Home.aspx/VemanaSatakam/ForeRunners/SumathiSatakam/ForeRunners/Pdf/DisplayContent.aspx?encry=ammkNW4%2Fgx+NeApstGPX+A%3D%3D)
- [Indexed Class 6–7 table](https://scert.telangana.gov.in/DisplayImage.aspx?encry=+J9U0B1hNdhJSYNXCM30vQ%3D%3D)
- Evidence: October 2026 indexed results show a “TEXT BOOKS (I TO X) - 2025-26” table and subject/medium rows for multiple classes, including Mathematics/science/social studies and several languages/media.
- Confidence medium-high for indexed listing; only medium for deep-link stability because these pages are dynamic/encoded. Verify actual destinations and current academic year on import.

### DIKSHA
- [Portal](https://diksha.gov.in/)
- [Government overview](https://pmevidya.education.gov.in/diksha.html)
- [Terms of use](https://diksha.gov.in/term-of-use.html)
- Evidence: official overview references QR-linked textbooks, class/region selection, Indian languages and offline support in DIKSHA's app. Terms discuss licensing/attribution.
- Confidence high for overview/terms. Verify licence per item; this research did not establish a stable unauthenticated public API contract for production catalogue search/download.

### Andhra Pradesh textbooks
- [Government title-wise downloads](https://cse.ap.gov.in/textBooksDownloadingPagetitleWise)
- [Academic-year/class/medium selector](https://cse.ap.gov.in/loadacademictextbookpublicview)
- [Minor-media bilingual list](https://cse.ap.gov.in/textBooksDownloadingPageMinorBilingual) and [Samagra Shiksha bilingual list](https://samagrashiksha.ap.gov.in/textBooksDownloadingPageTEBilingual).
- Evidence: indexed government pages expose class/subject/book-name tables and download links. This is a stronger starting point for automated catalogue discovery than guessing file paths, but direct files and rights must still be verified per item.
- Confidence: high that these are official resource pages; individual link stability/usage rights need per-item review.
- Direct link candidates taken from the official table: [Class 6 Maths SEM-1](https://cse.ap.gov.in/downloadBooks/Maths%20Books/6_Maths_SEM-1_Textbook.pdf/6), [Class 8 Maths SEM-1](https://cse.ap.gov.in/downloadBooks/Maths%20Books/8_Maths_SEM-1_Textbook.pdf/8), [Class 9 Maths SEM-1](https://cse.ap.gov.in/downloadBooks/Maths%20Books/9_Maths_SEM-1_Textbook.pdf/9), [Class 10 English](https://cse.ap.gov.in/downloadBooks/English%20Books/10_English_Textbook.pdf/10). Browser fetching returned an 803/timeout/404 for some direct endpoints in this research session; verify in a normal browser and mark them unusable until confirmed.

### Maharashtra eBalbharati
- [e-Book Library](https://books.ebalbharati.in/ebook.aspx) and [official home/licensing page](https://ebalbharati.in/main/publichome.aspx).
- Evidence: indexed catalogue exposes syllabus years (including 2026), classes 1–12, book types, subjects and many mediums including Marathi, Hindi, English, Urdu, Gujarati, Kannada, Sindhi, Telugu, Tamil and Bengali. The official home says PDFs are free to download and separately provides a licensing route for textbook content use.
- Confidence: high for the catalogue fields; permission to reuse is not implied by free download.

### Kerala SCERT
- [Official SCERT Kerala portal](https://scert.kerala.gov.in/).
- Evidence: current indexed notices include revised school textbooks for classes 6, 8 and 10 and curriculum materials for 2026–27. Exact download links, versions and allowed use need item-level review.
- Confidence: high for official portal, medium for individual link/edition state until verified.

### CBSE syllabus reference
- [CBSE Academic Curriculum 2026–27](https://cbseacademic.nic.in/curriculum_2027.html)
- Use for official subject/syllabus and academic-year metadata. A syllabus document is not automatically a textbook download licence.

## C. Offline/PWA/storage

### MDN — Background Synchronization API
- [API guide](https://developer.mozilla.org/en-US/docs/Web/API/Background_Synchronization_API)
- MDN marks it limited availability, not Baseline, and notes secure-context/support restrictions.
- Design consequence: reconnect/foreground/focus/manual sync is required even if Background Sync is optionally supported.
- Confidence high for platform caveat.

### web.dev — Offline data
- [Offline data guide](https://web.dev/learn/pwa/offline-data?hl=en)
- Describes IndexedDB for structured data/blobs and why WebStorage isn't suitable for complex synchronous data. Quotas vary by device/browser.

### MDN — storage quotas/eviction
- [Storage quota and eviction criteria](https://developer.mozilla.org/en-US/docs/Web/API/Storage_API/Storage_quotas_and_eviction_criteria)
- Browsers may evict best-effort storage; the Storage API offers estimates and persistent-storage request where supported. Never promise browser data is permanently safe.

### web.dev — serving/caching strategies
- [PWA serving guide](https://web.dev/learn/pwa/serving)
- Cache First / Network First / Stale While Revalidate are distinct strategies; choose by asset/data type. Do not indiscriminately cache private personalised API responses.

### Vite PWA
- [Vite PWA docs repository](https://github.com/vite-pwa/docs)
- Check current version and compatibility before implementing. The project documents Vite service-worker integrations/Workbox strategies.

### Supabase Storage
- [Access control](https://supabase.com/docs/guides/storage/security/access-control) — Storage policies use Postgres RLS for upload/read/list/delete.
- [Resumable uploads](https://supabase.com/docs/guides/storage/uploads/resumable-uploads) — TUS is recommended for larger files (docs cite >6 MB as a use case) or unstable connections. Verify current project limits.
- [Postgres RLS](https://supabase.com/docs/guides/database/postgres/row-level-security) and [secure data guide](https://supabase.com/docs/guides/database/secure-data) — service-role/secret keys can bypass RLS and must never be exposed in browser code.
- [Database migrations](https://supabase.com/docs/guides/deployment/database-migrations) and [local migrations](https://supabase.com/docs/guides/local-development/database-migrations) — use migrations as schema source of truth to prevent drift.

## D. Retrieval/AI/security

### pgvector
- [Official repository and docs](https://github.com/pgvector/pgvector)
- Exact nearest neighbour is a sensible baseline. HNSW/IVFFlat trade performance/recall/build/memory; approximate-index filtering can reduce matches. Test filtered recall before optimising.

### Ragas evaluation
- [Available metrics](https://docs.ragas.io/en/latest/concepts/metrics/available_metrics/)
- Includes context precision/recall, answer relevancy, faithfulness and factual correctness concepts. Metrics are only meaningful with a labelled dataset and defined scoring method.

### OWASP uploads
- [File Upload Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/File_Upload_Cheat_Sheet.html)
- Guidance includes allowlists, file-signature validation, safe filenames, limits, authorisation, isolated storage and parser hardening.

### OWASP prompt injection/RAG security
- [LLM01 prompt injection](https://genai.owasp.org/llmrisk/llm01-prompt-injection/)
- [RAG Security Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/RAG_Security_Cheat_Sheet.html)
- RAG does not eliminate injection risk; treat source text as data, enforce access, and validate outputs across ingestion/retrieval/generation.

### UNESCO
- [Guidance for generative AI in education and research](https://www.unesco.org/en/articles/guidance-generative-ai-education-and-research)
- Supports human-centred use, privacy protection and age-appropriate safeguards. This is guidance, not a substitute for applicable law/policy review.

## E. Copyright and imagery

### DIKSHA terms
- [Terms](https://diksha.gov.in/term-of-use.html). Check rights and attribution for each resource, not only platform-level messaging.

### Openverse
- [API](https://api.openverse.org/v1/) and [docs](https://docs.openverse.org/)
- Discovery for open-licensed media; inspect individual metadata, original landing page and licence.

### Creative Commons
- [Reuse guide](https://creativecommons.org/reusing-cc-licensed-content/)
- [Attribution best practice](https://wiki.creativecommons.org/wiki/Recommended_practices_for_attribution)
- Attribution is required by CC licences; title/creator/source/licence are recommended. Other conditions (ShareAlike, NonCommercial, NoDerivatives) matter.

### Unsplash API (optional only)
- [API docs](https://unsplash.com/documentation)
- [API guidelines](https://help.unsplash.com/en/articles/2511245-unsplash-api-guidelines)
- Hotlinking, attribution/links, rate limits and key confidentiality requirements apply. Not the default initial image provider; first-party SVG/Openverse with licence checks is the safer plan.

## F. Agent skills and MCP

### Agent Skills CLI
- [Skills docs](https://www.skills.sh/docs), [CLI docs](https://www.skills.sh/docs/cli), [npm package](https://www.npmjs.com/package/skills)
- `npx skills add ...` installs reusable skills and the CLI supports multiple agents. Check current supported agent/flags and review third-party skill sources before execution.

### Cursor MCP
- [Official Cursor MCP docs](https://cursor.com/docs/mcp)
- MCP exposes tools/data sources and can be configured through `mcp.json`; actual availability/approval depends on the runtime. The agent must report real tools used, not guessed names.

## G. Open validation needs

- Verify current Telangana SCERT year and exact resource download links at import time.
- Check item-level DIKSHA rights and API access/terms.
- Seek written permission/legal review for NCERT link/reuse conditions as relevant to public deployment.
- Review minor/student data handling and uploaded copyrighted materials before production deployment.
- Test quotas/offline behaviour on target Android browsers/low-end devices.
- Get LLM/embedder IDs and budgets from the actual environment/deployment, with secrets redacted.
