# SETU — Scoped Supabase Cleanup Report

**Generated:** 2026-10-30
**Database:** configured production Supabase project (URL and keys are never printed)
**Mode:** scoped auth/storage cleanup after verified backup; read-only final inventory
**Status:** COMPLETE (scoped), emergency full reset NOT RUN

## What was authorized

The user explicitly requested removal of legacy Supabase Auth users and stale
application Storage objects, with a backup and verification. No broad reset of
profiles, documents, learning data, classrooms, or doubts was authorized or
performed.

**Scope of this report:** the 2026-10-30 auth/storage pass. The earlier
2026-10-28 scoped cleanup deleted 8 `@example.com` profiles and 26 seeded
resource/rights rows; that history is recorded in sections 6–7 of
`context/SUPABASE_CLEANUP_MANIFEST.md`.

## Backup

| Artifact | Path | Size |
|---|---|---:|
| Public-schema SQL backup | `backend/backups/supabase_public_backup_20261030_091121.sql` | 16,014,307 bytes |
| Backup metadata | `backend/backups/supabase_manifest_20261030_091121.json` | 6,984 bytes |
| Archived orphan objects | `backend/backups/storage_orphans_20261030/` | 5 objects + `manifest.json` |

The backup was taken before deletion. Its manifest contains redacted auth-user
metadata, public table counts, bucket metadata, storage object names, and
extensions. It contains no password, service key, or full email address.

## Deleted auth users

Before: **9** `auth.users`.
After: **1** `auth.users` (the preserved Gmail account
`5cee4e2f-bbdc-41f5-87c9-52cdc63e755b`).

Deleted 8 orphan `@example.com` accounts by explicit ID:

```text
f067c249-63c3-4aeb-adef-5b2dfa658f6b
6042717d-3b28-43e7-99d6-e0ece1ff4094
4a50ddf8-b62e-4ac7-8cf2-bd0449a1b4a6
1a8f1578-415c-4c87-80b1-77ad5001a043
b461a060-28ac-40f4-99d8-a33de0c1441b
7b645ef0-9b7a-4ec5-9f18-8f3828bbd14e
d33bcb7c-380a-4b6a-968a-277c5a1089cc
b6a37ff1-88b0-4cd0-9018-f346b24f065f
```

An earlier cleanup log claimed these were already deleted, but their
`deleted_at` was still null. The Admin API deletes were re-run and verified.
No public application row referenced a deleted auth ID.

## Deleted storage objects

Before: **8** objects in `setu-documents`.
After: **3** objects.

Five orphan objects were first downloaded to
`backend/backups/storage_orphans_20261030/` with a SHA-256 manifest, then
deleted:

- Three copies of `NCERT-Class-10-Science.pdf` (16,240,856 bytes each,
  SHA-256 `fb04cf19f48fa2efa1e08854640826fffe47f6f6c7a4cbe983754a78dea2054f`).
- Two copies of
  `TS-SCERT-Class-10-Social-Science-Textbook-in-English-Medium.pdf`
  (19,533,190 bytes each, SHA-256
  `dea05fe59c127df137db907bc249b2bdf09ee27eacdc3e6124bd2299f97e6ea5`).

The three remaining objects all match current `documents.storage_key` values.
No bucket, policy, or referenced object was removed.

### Residual finding

Two older documents reference storage keys that are absent from the bucket:

```text
09aa8711-a71e-46fc-9d61-cebc22ea38f3/eval_cell.pdf
test/Class_9_Science_Chapter_5.pdf
```

They were already absent before this cleanup and were not deleted here. Their
extracted pages and chunks remain in PostgreSQL; only a future raw-file download
would be affected.

## Final read-only inventory

**Command:**

```powershell
.\backend\.venv\Scripts\python.exe backend\scripts\reset_supabase_app_data.py
```

**Observed final line:** `Read-only inventory. No changes were made.`
**Full log:** `context/PRODUCTION_INVENTORY_2026-10-30.log`

| Table | Rows |
|---|---:|
| `alembic_version` | 1 |
| `user_profiles` | 1 |
| `documents` | 13 |
| `document_pages` | 628 |
| `document_chunks` | 1086 |
| `learning_paths` | 1 |
| `path_lessons` | 24 |
| `lesson_versions` | 17 |
| `questions` | 0 |
| `quiz_attempts` | 0 |
| `concept_evidence` | 0 |
| `concept_mastery_snapshots` | 0 |
| `doubts` | 15 |
| `sync_events` | 0 |
| `classrooms` | 8 |
| `classroom_memberships` | 8 |
| `teacher_actions` | 0 |
| `study_events` | 6 |
| `generation_jobs` | 24 |
| `resources` | 0 |
| `resource_rights` | 0 |
| `resource_sources` | 0 |
| `curriculum_boards` | 6 |
| `subjects` | 6 |
| `languages` | 4 |
| `storage.objects` (`setu-documents`) | 3 |
| `auth.users` | 1 |

Public application tables: 25. The target host was printed masked; no secret or
full email was printed.

## Confirmation and safety

- **Scoped cleanup: COMPLETE.** Only the named auth IDs and the five orphan
  storage objects were deleted.
- **Emergency full reset: NOT RUN.** No command with
  `--confirm DROP-ALL-APPLICATION-TABLES` was executed.
- **Preserved:** the Gmail profile, 13 documents, 628 pages, 1086 chunks, 1
  learning path, 24 lessons, 17 versions, 15 doubts, 8 classrooms, 8
  memberships, 6 study events, 24 jobs, and all 3 referenced storage objects.
- **Open decision:** the preserved Gmail profile still has role `student` while
  owning 8 classrooms, so production teacher endpoints return 403. No role was
  changed without explicit approval.
- Detailed object names, SHA-256 values, and the full inventory are in
  `context/SUPABASE_CLEANUP_MANIFEST.md` section 8.
