# SETU Clean Database and Storage Reset Verification Report

- **Execution Timestamp:** 2026-10-28T07:07:40.213501+00:00
- **Target Supabase Host:** aws-0-ap-south-1.pooler.supabase.com (project mevbffduofdpalzimfye)
- **Backup Location:** `backend/backups/supabase_public_backup_20261028_070420.sql` (4.2 MB)
- **Backup Manifest:** `backend/backups/supabase_manifest_20261028_070420.json`

## 1. Dropped Legacy Application Tables (Clean Scope)

Total dropped tables: **32**

- `public.alembic_version`
- `public.catalogue_boards`
- `public.catalogue_subjects`
- `public.classroom_grants`
- `public.classroom_invitations`
- `public.classrooms`
- `public.concepts`
- `public.content_sources`
- `public.content_suggestions`
- `public.document_audit_events`
- `public.document_pages`
- `public.indexed_chunks`
- `public.indexed_documents`
- `public.interaction_events`
- `public.learner_mastery_states`
- `public.learner_model_applications`
- `public.learner_skill_beliefs`
- `public.learning_contexts`
- `public.prerequisite_edges`
- `public.processing_jobs`
- `public.question_items`
- `public.student_profiles`
- `public.syllabus_board_mediums`
- `public.syllabus_mediums`
- `public.syllabus_sources`
- `public.syllabus_topics`
- `public.teacher_decisions`
- `public.teacher_interventions`
- `public.teacher_invites`
- `public.teacher_observations`
- `public.teacher_overrides`
- `public.teacher_recommendations`

## 2. Cleared Storage Objects

- Legacy objects cleared via Storage API: **2**
- Storage bucket `setu-documents` preserved: **Yes** (private)

## 3. Preserved Infrastructure and Platform Schemas

- **Managed Schemas:** `auth`, `storage`, `vault`, `realtime`, `extensions`, `graphql`, `graphql_public`, `pgbouncer`
- **Extensions Intact:** pg_stat_statements, pg_trgm, pgcrypto, plpgsql, supabase_vault, uuid-ossp, vector
- **Auth Users Preserved:** 4 users
- **Remaining Public Tables:** 0 (0 remaining — verified clean)

## 4. Verification Verdict

**VERIFIED CLEAN:** Application schema is completely reset and ready for clean SETU Alembic migrations.
