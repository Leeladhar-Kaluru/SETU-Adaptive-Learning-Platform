import os
import json
import datetime
import psycopg

# Load DB URL from backend/.env safely
env_path = os.path.abspath("backend/.env")
db_url = None
with open(env_path, "r", encoding="utf-8") as f:
    for line in f:
        line = line.strip()
        if line.startswith("DATABASE_URL="):
            db_url = line.split("=", 1)[1].strip().strip('"').strip("'")

if not db_url:
    print("ERROR: DATABASE_URL not found in backend/.env")
    exit(1)

backup_dir = os.path.abspath("backend/backups")
os.makedirs(backup_dir, exist_ok=True)
timestamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d_%H%M%S")
sql_backup_path = os.path.join(backup_dir, f"supabase_public_backup_{timestamp}.sql")
manifest_path = os.path.join(backup_dir, f"supabase_manifest_{timestamp}.json")

print(f"Connecting to Supabase PostgreSQL at {timestamp}...")
conn = psycopg.connect(db_url)

manifest = {
    "timestamp": timestamp,
    "database_version": "",
    "schemas": [],
    "public_tables": {},
    "storage_buckets": [],
    "storage_objects": [],
    "auth_users_count": 0,
    "auth_users_redacted": [],
    "extensions": []
}

with conn.cursor() as cur:
    cur.execute("SELECT version();")
    manifest["database_version"] = cur.fetchone()[0]

    # Non-system schemas
    cur.execute("""
        SELECT schema_name 
        FROM information_schema.schemata 
        WHERE schema_name NOT IN ('information_schema', 'pg_catalog', 'pg_toast')
        ORDER BY schema_name;
    """)
    manifest["schemas"] = [r[0] for r in cur.fetchall()]

    # Extensions
    cur.execute("SELECT extname, extversion FROM pg_extension ORDER BY extname;")
    manifest["extensions"] = [{"name": r[0], "version": r[1]} for r in cur.fetchall()]

    # Storage buckets & objects
    try:
        cur.execute("SELECT id, name, public, created_at FROM storage.buckets;")
        manifest["storage_buckets"] = [{"id": r[0], "name": r[1], "public": r[2]} for r in cur.fetchall()]
        
        cur.execute("SELECT id, name, bucket_id, owner, created_at, metadata FROM storage.objects;")
        manifest["storage_objects"] = [
            {"id": str(r[0]), "name": r[1], "bucket_id": r[2], "created_at": str(r[4]), "size": r[5].get("size") if isinstance(r[5], dict) else None}
            for r in cur.fetchall()
        ]
    except Exception as e:
        print(f"Warning storage query: {e}")
        conn.rollback()

    # Auth users
    try:
        cur.execute("SELECT count(*) FROM auth.users;")
        manifest["auth_users_count"] = cur.fetchone()[0]
        cur.execute("SELECT id, email, created_at FROM auth.users;")
        for u in cur.fetchall():
            email = u[1] or ""
            domain = email.split("@")[-1] if "@" in email else ""
            prefix = email[:2] if email else ""
            manifest["auth_users_redacted"].append({
                "id": str(u[0]),
                "email_redacted": f"{prefix}***@{domain}",
                "created_at": str(u[2])
            })
    except Exception as e:
        print(f"Warning auth query: {e}")
        conn.rollback()

    # Public tables dynamic inventory
    cur.execute("""
        SELECT table_name 
        FROM information_schema.tables 
        WHERE table_schema = 'public' 
        ORDER BY table_name;
    """)
    public_tables = [r[0] for r in cur.fetchall()]

    print(f"Found {len(public_tables)} tables in 'public' schema. Dumping data and schema...")
    with open(sql_backup_path, "w", encoding="utf-8") as sql_file:
        sql_file.write(f"-- Supabase public schema backup taken at {timestamp}\n")
        sql_file.write(f"-- PostgreSQL Version: {manifest['database_version']}\n\n")

        for table in public_tables:
            cur.execute(f'SELECT count(*) FROM "public"."{table}";')
            cnt = cur.fetchone()[0]
            manifest["public_tables"][table] = cnt
            print(f"  Backing up public.{table} ({cnt} rows)...")

            # Write table comment
            sql_file.write(f"\n-- Table: public.{table} ({cnt} rows)\n")
            
            # Export column info
            cur.execute("""
                SELECT column_name, data_type, is_nullable
                FROM information_schema.columns
                WHERE table_schema = 'public' AND table_name = %s
                ORDER BY ordinal_position;
            """, (table,))
            columns = cur.fetchall()
            col_names = [f'"{c[0]}"' for c in columns]

            if cnt > 0:
                cur.execute(f'SELECT * FROM "public"."{table}";')
                rows = cur.fetchall()
                for row in rows:
                    vals = []
                    for val in row:
                        if val is None:
                            vals.append("NULL")
                        elif isinstance(val, (int, float)):
                            vals.append(str(val))
                        elif isinstance(val, bool):
                            vals.append("TRUE" if val else "FALSE")
                        elif isinstance(val, (dict, list)):
                            s = json.dumps(val).replace("'", "''")
                            vals.append(f"'{s}'::jsonb")
                        else:
                            s = str(val).replace("'", "''")
                            vals.append(f"'{s}'")
                    sql_file.write(f'INSERT INTO "public"."{table}" ({", ".join(col_names)}) VALUES ({", ".join(vals)});\n')

with open(manifest_path, "w", encoding="utf-8") as f:
    json.dump(manifest, f, indent=2)

print("\nBackup complete!")
print(f"  SQL dump: {sql_backup_path} ({os.path.getsize(sql_backup_path)} bytes)")
print(f"  Manifest: {manifest_path} ({os.path.getsize(manifest_path)} bytes)")

conn.close()

