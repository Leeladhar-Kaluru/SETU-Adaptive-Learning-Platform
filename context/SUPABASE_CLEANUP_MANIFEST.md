# SETU — Supabase Controlled Cleanup Manifest

**Execution Timestamp:** 2026-10-28T13:33:40.076228 UTC
**Target Supabase Project:** https://mevbffduofdpalzimfye.supabase.co
**Storage Bucket:** setu-documents

> **Current state (2026-10-29):** Sections 1–5 are the historical full-reset record.
> Section 6 is the pre-cleanup inventory. Section 7 is the final read-only
> inventory after the approved scoped cleanup and Task 17 verification. No broad
> reset and no emergency `--apply` reset was run.

---

## 1. Initial State Inventory
- `teacher_actions`: 0 rows
- `classroom_memberships`: 7 rows
- `study_events`: 4 rows
- `quiz_attempts`: 0 rows
- `concept_mastery_snapshots`: 0 rows
- `concept_evidence`: 0 rows
- `sync_events`: 0 rows
- `doubts`: 14 rows
- `lesson_versions`: 16 rows
- `generation_jobs`: 24 rows
- `path_lessons`: 27 rows
- `learning_paths`: 4 rows
- `document_chunks`: 2956 rows
- `document_pages`: 1248 rows
- `documents`: 17 rows
- `classrooms`: 12 rows
- `user_profiles`: 7 rows

## 2. Deleted Legacy Auth Users

## 3. Deleted Storage Objects (4 items)
- Object path: `documents`
- Object path: `documents/382d0709-4c58-461f-9665-6441a5e5b31f`
- Object path: `documents/68c5ae2c-e188-4d4e-93fb-dccdceb40349`
- Object path: `documents/de898934-3c24-4d3a-baf3-53387ac557b0`

## 4. Post-Cleanup Verification Counts
- `teacher_actions`: 0 rows
- `classroom_memberships`: 0 rows
- `study_events`: 0 rows
- `quiz_attempts`: 0 rows
- `concept_mastery_snapshots`: 0 rows
- `concept_evidence`: 0 rows
- `sync_events`: 0 rows
- `doubts`: 0 rows
- `lesson_versions`: 0 rows
- `generation_jobs`: 0 rows
- `path_lessons`: 0 rows
- `learning_paths`: 0 rows
- `document_chunks`: 0 rows
- `document_pages`: 0 rows
- `documents`: 0 rows
- `classrooms`: 0 rows
- `user_profiles`: 0 rows

## 5. Verification Result
- Status: SUCCESS (100% Cleared)
- Database schemas, migrations, triggers, and RLS policies remain 100% intact.
- Service role keys and secrets were NOT printed or logged.

---

## 6. Clean-Product Scoped Cleanup Inventory (2026-10-28)

**Command:** `.\backend\.venv\Scripts\python.exe backend\scripts\cleanup_demo_data.py --inventory`
**Mode:** read-only inventory. **`--apply`:** NOT RUN.
**Human confirmation gate:** **OPEN**.

### 6.1 Current Row Counts

| Table | Rows |
|---|---:|
| `user_profiles` | 9 |
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
| `resources` | 26 |
| `resource_rights` | 26 |
| `storage.objects` (`setu-documents`) | 8 |

**Profiles by domain:** `example.com`: 8, `gmail.com`: 1.

### 6.2 Profile IDs and Masked Emails

| Profile ID | Masked email | Domain | Test-domain heuristic | Role |
|---|---|---|---|---|
| `1a8f1578-415c-4c87-80b1-77ad5001a043` | `s***@example.com` | example.com | yes | student |
| `4a50ddf8-b62e-4ac7-8cf2-bd0449a1b4a6` | `s***@example.com` | example.com | yes | student |
| `b461a060-28ac-40f4-99d8-a33de0c1441b` | `s***@example.com` | example.com | yes | student |
| `7b645ef0-9b7a-4ec5-9f18-8f3828bbd14e` | `s***@example.com` | example.com | yes | student |
| `d33bcb7c-380a-4b6a-968a-277c5a1089cc` | `s***@example.com` | example.com | yes | student |
| `5cee4e2f-bbdc-41f5-87c9-52cdc63e755b` | `c***@gmail.com` | gmail.com | no | student |
| `b6a37ff1-88b0-4cd0-9018-f346b24f065f` | `s***@example.com` | example.com | yes | student |
| `f067c249-63c3-4aeb-adef-5b2dfa658f6b` | `s***@example.com` | example.com | yes | student |
| `6042717d-3b28-43e7-99d6-e0ece1ff4094` | `s***@example.com` | example.com | yes | student |

The `gmail.com` profile (`5cee4e2f-...`, masked `c***@gmail.com`) is the likely
real account, but **the human has not confirmed it**. The eight `example.com`
profiles are candidates only; the test-domain heuristic is not authorization.

### 6.3 Truthful State Notes

- `resources` and `resource_rights` still contain 26 rows each. Migration `006`
  has not been applied to this database yet. On apply, the cleanup safety net
  clears `documents.resource_id` references and deletes the 26 seeded resource
  IDs and their rights.
- `storage.objects` contains 8 objects in `setu-documents`, not the 13 implied
  by the document count. This is the observed value, not an estimate.
- No rows, storage objects, or `auth.users` were deleted by the inventory run.
- The script has no inventory-time Admin API call and never prints
  `DATABASE_URL`, service keys, or full email addresses.

### 6.4 Required Apply Gate

Apply remains blocked until the human explicitly names the demo profile IDs and
the real `gmail.com` profile ID. The eventual command must include:

```
python backend/scripts/cleanup_demo_data.py --apply --confirm APPLY-CLEANUP \
  --delete-user-id <demo-uuid> [--delete-user-id <demo-uuid> ...] \
  --preserve-user-id <real-gmail-uuid>
```

The report from the inventory run is at `context/CLEANUP_REPORT.md`. That file
records the same counts and masked emails and states that the gate is open.

---

## 7. Final inventory after scoped cleanup (2026-10-29)

**Command:** `.\backend\.venv\Scripts\python.exe backend\scripts\reset_supabase_app_data.py`
**Mode:** read-only inventory. The script printed `Read-only inventory. No changes were made.`
**Emergency reset `--apply`:** NOT RUN.
**Scoped cleanup:** applied earlier under Task 2 with explicit profile IDs. Eight
`example.com` profiles and the 26 seeded `resources` / `resource_rights` rows were
deleted. The real Gmail profile (`5cee4e2f-bbdc-41f5-87c9-52cdc63e755b`) was
preserved.

### 7.1 Observed row counts

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
| `storage.objects` (`setu-documents`) | 8 |
| `auth.users` | 9 |

### 7.2 Confirmation state

- The scoped cleanup confirmation gate is **closed** for the eight
  `example.com` profiles and the seeded resources; those rows are gone.
- The emergency reset gate remains **closed**. No command with
  `--confirm DROP-ALL-APPLICATION-TABLES` was executed.
- A new decision is **open**: `auth.users` still has 9 rows while
  `user_profiles` has 1. Eight auth users are therefore orphans from the scoped
  profile deletion. They were intentionally not deleted without explicit human
  authorization and a verified backup.
- `storage.objects` has 8 objects for 13 documents. This is the observed value.
  Do not infer missing objects from the document count without checking storage
  keys per document.
- The preserved Gmail profile has role `student` and owns 8 classrooms. Teacher
  endpoints return 403 for that account until its role is corrected or a real
  teacher account is used. No role was changed during this verification.

### 7.3 Safety notes

- The inventory run did not print the database URL, password, service key, or
  full email addresses. The target was shown as a masked pooler host.
- No application table, storage object, profile, or auth user was changed by the
  Task 17 inventory.
- The timestamped reset-report mechanism is covered by
  `backend/tests/test_reset_guard.py`; no report is produced by a read-only run.
