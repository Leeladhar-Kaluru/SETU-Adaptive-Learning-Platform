"""Adversarial Verification Script for Milestone 1: Supabase Clean Reset.

Empirically tests and verifies against the live Supabase instance:
1. Alembic version is intact at '008'.
2. All 15 target application tables have exactly 0 rows.
3. All 7 auth.users and 7 public.user_profiles are preserved, uncorrupted, and 1:1 mapped.
4. Reference curriculum taxonomy (boards, subjects, languages) is intact.
5. All foreign keys in public schema have 0 orphaned rows.
6. Storage bucket 'setu-documents' exists and contains 0 objects in DB and via REST API.
7. Backup snapshot and manifest files exist, are valid, and complete.
8. Entire public schema table inventory is accounted for.
"""
from __future__ import annotations

import json
import os
import sys
import urllib.request
from pathlib import Path
from typing import Any

import psycopg

BACKEND_DIR = Path(__file__).resolve().parents[1]
ENV_FILE = BACKEND_DIR / ".env"


def get_config() -> dict[str, str]:
    config: dict[str, str] = {}
    if ENV_FILE.is_file():
        for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            config[k.strip()] = v.strip().strip('"').strip("'")
    for k in ("DATABASE_URL", "SUPABASE_URL", "SUPABASE_SECRET_KEY"):
        if os.environ.get(k):
            config[k] = os.environ[k]
    return config


def run_checks():
    config = get_config()
    db_url = config.get("DATABASE_URL")
    if not db_url:
        print("ERROR: DATABASE_URL not found!")
        sys.exit(1)

    print("============================================================")
    print("ADVERSARIAL VERIFICATION HARNESS — MILESTONE 1")
    print("Connecting to database...")
    print("============================================================")

    failures: list[str] = []
    successes: list[str] = []

    conn = psycopg.connect(db_url, prepare_threshold=None)

    with conn.cursor() as cur:
        # Check 1: Alembic Version
        print("\n[Check 1/8] Verifying Alembic Version...")
        cur.execute("SELECT version_num FROM alembic_version;")
        rows = cur.fetchall()
        if len(rows) == 1 and rows[0][0] == "008":
            msg = f"Alembic version is intact: head is '{rows[0][0]}'"
            print(f"  [PASS] {msg}")
            successes.append(msg)
        else:
            msg = f"Alembic version unexpected: {rows}"
            print(f"  [FAIL] {msg}")
            failures.append(msg)

        # Check 2: Auth Users
        print("\n[Check 2/8] Verifying auth.users preservation...")
        expected_user_ids = {
            "5cee4e2f-bbdc-41f5-87c9-52cdc63e755b",
            "81c1fea7-bc15-4eb9-af67-bc63734505b3",
            "f3ac32c7-1fd7-4762-9248-d0e2159f1512",
            "4d17a08b-5627-46a2-868e-df3ebf500c53",
            "2acb9a1e-547d-49be-8c44-1e499ac3307f",
            "202a3d0a-df08-4242-91fb-4e95636581e5",
            "50f42b4f-c778-492e-821c-3707eff1fd3e",
        }
        cur.execute("SELECT id, email, created_at, encrypted_password FROM auth.users ORDER BY created_at;")
        auth_rows = cur.fetchall()
        actual_user_ids = {str(r[0]) for r in auth_rows}
        if len(auth_rows) == 7 and actual_user_ids == expected_user_ids:
            msg = f"All 7 auth.users verified intact. IDs match baseline exactly."
            print(f"  [PASS] {msg}")
            for r in auth_rows:
                email_mask = r[1][:2] + "***@" + r[1].split("@")[-1] if r[1] else "no-email"
                print(f"         User {r[0]} | Email: {email_mask} | Created: {r[2]}")
            successes.append(msg)
        else:
            msg = f"auth.users count ({len(auth_rows)}) or IDs mismatch: missing {expected_user_ids - actual_user_ids}, extra {actual_user_ids - expected_user_ids}"
            print(f"  [FAIL] {msg}")
            failures.append(msg)

        # Check 3: User Profiles
        print("\n[Check 3/8] Verifying public.user_profiles preservation...")
        expected_profiles = {
            "5cee4e2f-bbdc-41f5-87c9-52cdc63e755b": ("student", "Chotu1"),
            "81c1fea7-bc15-4eb9-af67-bc63734505b3": ("teacher", "Meera Rao"),
            "f3ac32c7-1fd7-4762-9248-d0e2159f1512": ("student", "Chotu2"),
            "4d17a08b-5627-46a2-868e-df3ebf500c53": ("teacher", "teacher1"),
            "2acb9a1e-547d-49be-8c44-1e499ac3307f": ("student", "Rahul"),
            "202a3d0a-df08-4242-91fb-4e95636581e5": ("student", "Chotu4"),
            "50f42b4f-c778-492e-821c-3707eff1fd3e": ("student", "Ramesh"),
        }
        cur.execute("SELECT id, email, role, display_name, created_at FROM public.user_profiles ORDER BY created_at;")
        profile_rows = cur.fetchall()
        profile_map = {str(r[0]): (r[2], r[3]) for r in profile_rows}
        if len(profile_rows) == 7 and profile_map == expected_profiles:
            msg = f"All 7 user_profiles verified intact. Roles and names match baseline exactly."
            print(f"  [PASS] {msg}")
            for r in profile_rows:
                print(f"         Profile {r[0]} | Role: {r[2]} | Name: {r[3]}")
            successes.append(msg)
        else:
            msg = f"user_profiles count ({len(profile_rows)}) or data mismatch: {profile_map} != {expected_profiles}"
            print(f"  [FAIL] {msg}")
            failures.append(msg)

        # Check 4: Purged Application Tables (Reverse-topological target set)
        print("\n[Check 4/8] Verifying target application tables are strictly 0 rows...")
        target_tables = [
            "coach_notes",
            "study_events",
            "sync_events",
            "concept_evidence",
            "concept_mastery_snapshots",
            "quiz_attempts",
            "questions",
            "doubts",
            "generation_jobs",
            "lesson_versions",
            "path_lessons",
            "learning_paths",
            "document_chunks",
            "document_pages",
            "documents",
        ]
        all_cleared = True
        for t in target_tables:
            cur.execute(f'SELECT count(*) FROM "public"."{t}";')
            cnt = cur.fetchone()[0]
            if cnt == 0:
                print(f"  [PASS] public.{t:<26} : 0 rows")
            else:
                msg = f"public.{t} contains {cnt} residual rows!"
                print(f"  [FAIL] {msg}")
                failures.append(msg)
                all_cleared = False
        if all_cleared:
            successes.append("All 15 target application tables are 100% empty (0 rows).")

        # Check 5: Complete Public Schema Table Audit
        print("\n[Check 5/8] Auditing ALL base tables in public schema...")
        cur.execute(
            """
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
            ORDER BY table_name;
            """
        )
        all_tables = [r[0] for r in cur.fetchall()]
        print(f"  Found {len(all_tables)} base tables in public schema:")
        for t in all_tables:
            cur.execute(f'SELECT count(*) FROM "public"."{t}";')
            cnt = cur.fetchone()[0]
            print(f"    - {t:<28} : {cnt} rows")

        # Reference taxonomy check
        cur.execute("SELECT count(*) FROM public.curriculum_boards;")
        boards = cur.fetchone()[0]
        cur.execute("SELECT count(*) FROM public.subjects;")
        subjects = cur.fetchone()[0]
        cur.execute("SELECT count(*) FROM public.languages;")
        languages = cur.fetchone()[0]
        if boards == 6 and subjects == 6 and languages == 4:
            msg = f"Curriculum taxonomy intact: 6 boards, 6 subjects, 4 languages."
            print(f"  [PASS] {msg}")
            successes.append(msg)
        else:
            msg = f"Curriculum taxonomy altered: boards={boards}, subjects={subjects}, languages={languages}"
            print(f"  [FAIL] {msg}")
            failures.append(msg)

        # Check 6: Foreign Key Referential Integrity / Orphan Search
        print("\n[Check 6/8] Searching for orphaned rows across ALL foreign keys in public schema...")
        cur.execute(
            """
            SELECT
                tc.table_name,
                kcu.column_name,
                ccu.table_name AS foreign_table_name,
                ccu.column_name AS foreign_column_name
            FROM
                information_schema.table_constraints AS tc
                JOIN information_schema.key_column_usage AS kcu
                  ON tc.constraint_name = kcu.constraint_name
                  AND tc.table_schema = kcu.table_schema
                JOIN information_schema.constraint_column_usage AS ccu
                  ON ccu.constraint_name = tc.constraint_name
                  AND ccu.table_schema = tc.table_schema
            WHERE tc.constraint_type = 'FOREIGN KEY' AND tc.table_schema = 'public'
            ORDER BY tc.table_name, kcu.column_name;
            """
        )
        fks = cur.fetchall()
        print(f"  Auditing {len(fks)} foreign key constraints for orphaned references...")
        orphan_found = False
        for table, col, ftable, fcol in fks:
            cur.execute(
                f"""
                SELECT count(*)
                FROM "public"."{table}" t
                WHERE t."{col}" IS NOT NULL
                  AND NOT EXISTS (
                    SELECT 1 FROM "public"."{ftable}" ft WHERE ft."{fcol}" = t."{col}"
                  );
                """
            )
            orphan_count = cur.fetchone()[0]
            if orphan_count > 0:
                msg = f"ORPHAN DETECTED: {table}.{col} -> {ftable}.{fcol} has {orphan_count} orphaned rows!"
                print(f"  [FAIL] {msg}")
                failures.append(msg)
                orphan_found = True
        if not orphan_found:
            msg = f"All {len(fks)} foreign key constraints in public schema verified: 0 orphaned rows."
            print(f"  [PASS] {msg}")
            successes.append(msg)

        # Check 7: Storage Bucket and Objects
        print("\n[Check 7/8] Verifying storage.objects and REST API...")
        cur.execute("SELECT id, name, public FROM storage.buckets WHERE id = 'setu-documents';")
        bucket_row = cur.fetchone()
        if bucket_row:
            print(f"  [PASS] Bucket 'setu-documents' exists (public={bucket_row[2]}).")
        else:
            failures.append("Bucket 'setu-documents' not found in storage.buckets!")

        cur.execute("SELECT count(*) FROM storage.objects WHERE bucket_id = 'setu-documents';")
        obj_count = cur.fetchone()[0]
        if obj_count == 0:
            msg = f"storage.objects has 0 rows for 'setu-documents'."
            print(f"  [PASS] {msg}")
            successes.append(msg)
        else:
            msg = f"storage.objects has {obj_count} remaining objects in 'setu-documents'!"
            print(f"  [FAIL] {msg}")
            failures.append(msg)

        # Storage REST API verification
        base_url = (config.get("SUPABASE_URL") or "").rstrip("/")
        secret = config.get("SUPABASE_SECRET_KEY") or ""
        if base_url and secret:
            if not base_url.startswith("http"):
                base_url = f"https://{base_url}"
            endpoint = f"{base_url}/storage/v1/object/list/setu-documents"
            headers = {
                "apikey": secret,
                "Authorization": f"Bearer {secret}",
                "Content-Type": "application/json",
            }
            payload = json.dumps({"prefix": "", "limit": 100}).encode("utf-8")
            req = urllib.request.Request(endpoint, data=payload, headers=headers, method="POST")
            try:
                with urllib.request.urlopen(req, timeout=30) as resp:
                    api_data = json.loads(resp.read().decode("utf-8"))
                    if len(api_data) == 0:
                        msg = "Supabase Storage REST API confirmed empty bucket (0 objects)."
                        print(f"  [PASS] {msg}")
                        successes.append(msg)
                    else:
                        msg = f"Supabase Storage REST API returned {len(api_data)} objects: {api_data}"
                        print(f"  [FAIL] {msg}")
                        failures.append(msg)
            except Exception as e:
                msg = f"Storage REST API query failed: {e}"
                print(f"  [FAIL] {msg}")
                failures.append(msg)

    conn.close()

    # Check 8: Backup Snapshot Integrity
    print("\n[Check 8/8] Verifying backup snapshot and manifest files...")
    backups_dir = BACKEND_DIR / "backups"
    if backups_dir.is_dir():
        manifests = list(backups_dir.glob("supabase_manifest_*.json"))
        sql_backups = list(backups_dir.glob("supabase_application_backup_*.sql"))
        if manifests and sql_backups:
            latest_manifest = sorted(manifests)[-1]
            latest_sql = sorted(sql_backups)[-1]
            try:
                mdata = json.loads(latest_manifest.read_text(encoding="utf-8"))
                sql_size = latest_sql.stat().st_size
                print(f"  Manifest file: {latest_manifest.name} ({latest_manifest.stat().st_size} bytes)")
                print(f"  SQL dump file: {latest_sql.name} ({sql_size} bytes)")
                if mdata.get("auth_users_count") == 7 and mdata.get("user_profiles_count") == 7 and sql_size > 10_000_000:
                    msg = f"Backup snapshot verified: SQL backup size {sql_size} bytes, manifest auth/profile counts = 7."
                    print(f"  [PASS] {msg}")
                    successes.append(msg)
                else:
                    msg = f"Backup files suspect: sql_size={sql_size}, manifest={mdata}"
                    print(f"  [FAIL] {msg}")
                    failures.append(msg)
            except Exception as e:
                msg = f"Backup verification error: {e}"
                print(f"  [FAIL] {msg}")
                failures.append(msg)
        else:
            failures.append("No backup manifest or SQL file found in backend/backups!")
    else:
        failures.append("backend/backups directory missing!")

    # Summary
    print("\n============================================================")
    print("VERIFICATION SUMMARY")
    print(f"Total Passed Checks: {len(successes)}")
    print(f"Total Failed Checks: {len(failures)}")
    print("============================================================")
    if failures:
        print("\nFAILURES ENCOUNTERED:")
        for f in failures:
            print(f"  - {f}")
        print("\nVERDICT: REQUEST_CHANGES")
        sys.exit(1)
    else:
        print("\nALL VERIFICATIONS PASSED CLEANLY.")
        print("VERDICT: APPROVE")
        sys.exit(0)


if __name__ == "__main__":
    run_checks()
