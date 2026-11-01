# SETU Clean Database and Storage Reset Verification Report

- **Execution Timestamp:** 2026-11-01T13:10:12.916572+00:00
- **Target Supabase Host:** aws-***.pooler.supabase.com/postgres
- **Backup SQL Snapshot:** `C:/projects/setu - V2/backend/backups/supabase_application_backup_20261101_130956.sql` (42220465 bytes)
- **Backup Manifest:** `C:/projects/setu - V2/backend/backups/supabase_manifest_20261101_130956.json`

## 1. Application Tables Clean Scope (Reverse-Topological Order)

Total cleaned tables: **15**

| Table Name | Before Clean | After Clean | Status |
|---|---:|---:|---|
| `public.coach_notes` | 0 | 0 | CLEARED (0 rows) |
| `public.study_events` | 28 | 0 | CLEARED (0 rows) |
| `public.sync_events` | 0 | 0 | CLEARED (0 rows) |
| `public.concept_evidence` | 19 | 0 | CLEARED (0 rows) |
| `public.concept_mastery_snapshots` | 13 | 0 | CLEARED (0 rows) |
| `public.quiz_attempts` | 17 | 0 | CLEARED (0 rows) |
| `public.questions` | 252 | 0 | CLEARED (0 rows) |
| `public.doubts` | 23 | 0 | CLEARED (0 rows) |
| `public.generation_jobs` | 124 | 0 | CLEARED (0 rows) |
| `public.lesson_versions` | 83 | 0 | CLEARED (0 rows) |
| `public.path_lessons` | 124 | 0 | CLEARED (0 rows) |
| `public.learning_paths` | 10 | 0 | CLEARED (0 rows) |
| `public.document_chunks` | 3,140 | 0 | CLEARED (0 rows) |
| `public.document_pages` | 1,871 | 0 | CLEARED (0 rows) |
| `public.documents` | 21 | 0 | CLEARED (0 rows) |

## 2. Cleared Storage Objects

- **Storage Bucket:** `setu-documents` (private, preserved)
- **Objects Before Clean:** 11
- **Objects Purged via REST API:** 11
- **Objects After Clean:** 0
- **Bucket Status:** **VERIFIED EMPTY (0 objects)**

## 3. Preserved Infrastructure, Reference Taxonomy & User Accounts

### 3.1 Preserved User Accounts & Profiles
- **Total `auth.users` Preserved:** 7
- **Total `public.user_profiles` Preserved:** 7

| User ID | Email (Redacted) | Profile Role | Profile Name | Created At |
|---|---|---|---|---|
| `5cee4e2f-bbdc-41f5-87c9-52cdc63e755b` | `ch***@gmail.com` | student | Chotu1 | 2026-10-28 14:40:42.996441+00:00 |
| `81c1fea7-bc15-4eb9-af67-bc63734505b3` | `se***@gmail.com` | teacher | Meera Rao | 2026-10-31 14:45:02.898079+00:00 |
| `f3ac32c7-1fd7-4762-9248-d0e2159f1512` | `ch***@gmail.com` | student | Chotu2 | 2026-10-31 16:22:52.809765+00:00 |
| `4d17a08b-5627-46a2-868e-df3ebf500c53` | `te***@gmail.com` | teacher | teacher1 | 2026-11-01 06:23:31.264526+00:00 |
| `2acb9a1e-547d-49be-8c44-1e499ac3307f` | `ch***@gmail.com` | student | Rahul | 2026-11-01 10:12:18.538783+00:00 |
| `202a3d0a-df08-4242-91fb-4e95636581e5` | `ch***@gmail.com` | student | Chotu4 | 2026-11-01 11:39:01.431771+00:00 |
| `50f42b4f-c778-492e-821c-3707eff1fd3e` | `ra***@gmail.com` | student | Ramesh | 2026-11-01 12:21:50.283566+00:00 |

### 3.2 Preserved Reference Taxonomy
- `public.curriculum_boards`: 6 rows (CBSE, ICSE, Karnataka, Maharashtra, Tamil Nadu, Uttar Pradesh)
- `public.subjects`: 6 rows (English, Mathematics, Science, Social Science, Hindi, Computer Science)
- `public.languages`: 4 rows (en, hi, ta, kn)
- `public.alembic_version`: 1 row (head '008') preserved intact

### 3.3 Preserved Managed Platform Schemas
- `auth` (27 tables): Preserved 100% without modification
- `storage` (8 tables): Storage configuration and policies preserved; only objects in `setu-documents` purged
- `vault`: Preserved
- `realtime`: Preserved
- `extensions`: Preserved (`vector` 0.8.0, `uuid-ossp`, `pgcrypto`, `pg_trgm`, `pg_stat_statements`, `plpgsql`, `supabase_vault`)
- `graphql`, `graphql_public`, `pgbouncer`: Platform infrastructure preserved

## 4. Verification Verdict

**VERIFIED CLEAN**: All 15 application tables and storage objects successfully reset to 0 in an atomic reverse-topological transaction. All 7 auth users, 7 user profiles, curriculum taxonomy, and platform schemas strictly preserved per AGENTS.md Rule 11.
