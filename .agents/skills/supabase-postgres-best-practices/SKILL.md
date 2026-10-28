---
name: supabase-postgres-best-practices
description: Best practices for Supabase PostgreSQL, schema migrations, pgvector, full-text search, and Row Level Security.
---

# Supabase & PostgreSQL Best Practices Skill

1. Repeatable forward-only migrations via Alembic: track migration versions, never alter production tables ad-hoc without a versioned migration.
2. Vector storage with pgvector:
   - Always probe and confirm embedding dimension before creating the table/column (confirmed 768d for nomic-embed).
   - Use cosine distance (`<=>`) for normalized embeddings.
   - Combine with PostgreSQL full-text search (`tsvector` + GIN index) for robust hybrid retrieval.
3. Row Level Security (RLS):
   - Enable RLS on all student-owned and teacher tables.
   - Ensure student can only SELECT/INSERT/UPDATE their own documents, chunks, attempts, and doubts.
   - Authorize teachers via explicit `classroom_memberships`.
4. Transactional safety:
   - Atomic job claiming using `SELECT ... FOR UPDATE SKIP LOCKED` with lease expiration.
   - Unique constraints on idempotency keys: `UNIQUE (owner_id, client_doubt_id)`, `UNIQUE (owner_id, client_event_id)`, `UNIQUE (idempotency_key)`.
5. Infrastructure preservation:
   - Never drop managed schemas (`auth`, `storage`, `vault`, `realtime`, `extensions`).
   - Clean only application-owned tables in `public`.
