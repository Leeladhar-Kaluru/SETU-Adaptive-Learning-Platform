"""Emergency application-data reset for a SETU database.

This tool is deliberately hard to run:

1. ``--confirm DROP-ALL-APPLICATION-TABLES``
2. ``--backup <non-empty dump file>``
3. ``--allow-production SETU-PRODUCTION-RESET``

Without ``--apply`` it only prints a read-only inventory. It never drops the
managed Supabase schemas (auth, storage, vault, realtime, extensions, graphql,
graphql_public, pgbouncer) and never prints a password or secret key.
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import re
import urllib.request
from pathlib import Path

CONFIRMATION = "DROP-ALL-APPLICATION-TABLES"
PRODUCTION_CONFIRMATION = "SETU-PRODUCTION-RESET"
MANAGED_SCHEMAS = {
    "auth",
    "storage",
    "vault",
    "realtime",
    "extensions",
    "graphql",
    "graphql_public",
    "pgbouncer",
    "information_schema",
    "pg_catalog",
    "pg_toast",
}


def require_reset_confirmation(args: argparse.Namespace) -> None:
    if args.confirm != CONFIRMATION:
        raise SystemExit(f"Refusing to reset. Pass --confirm {CONFIRMATION}.")
    backup = Path(args.backup or "")
    if not backup.is_file() or backup.stat().st_size == 0:
        raise SystemExit("Refusing to reset. --backup must point to a non-empty database dump.")
    if args.allow_production != PRODUCTION_CONFIRMATION:
        raise SystemExit(
            f"Refusing to reset. Pass --allow-production {PRODUCTION_CONFIRMATION} "
            "after verifying the backup and the target project."
        )


def parse_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.is_file():
        return values
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def resolve_config(env_file: Path | None) -> dict[str, str]:
    values = parse_env_file(env_file or Path(__file__).resolve().parents[1] / ".env")
    for key in ("DATABASE_URL", "SUPABASE_URL", "SUPABASE_SECRET_KEY"):
        if os.environ.get(key):
            values[key] = os.environ[key]
    return values


def masked_host(database_url: str) -> str:
    """Return host/database with a pooled project reference masked."""
    match = re.match(r"^[a-z0-9+]+://[^@/]+@([^/]+)/([^?]+)", database_url, re.IGNORECASE)
    if not match:
        return "unknown"
    host, database = match.group(1), match.group(2)
    if ".pooler.supabase.com" in host:
        host = host.split(".pooler.supabase.com")[0]
        host = f"{host[:4]}***.pooler.supabase.com"
    elif ".supabase.co" in host:
        host = host.split(".supabase.co")[0]
        host = f"{host[:4]}***.supabase.co"
    return f"{host}/{database}"


def public_tables(cur) -> list[str]:
    cur.execute(
        """
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
        ORDER BY table_name;
        """
    )
    return [row[0] for row in cur.fetchall()]


def table_counts(cur, tables: list[str]) -> dict[str, int | str]:
    counts: dict[str, int | str] = {}
    for table in tables:
        try:
            cur.execute(f'SELECT count(*) FROM "public"."{table}";')
            counts[table] = cur.fetchone()[0]
        except Exception:
            counts[table] = "unknown"
    return counts


def safe_scalar(cur, sql: str) -> int | str:
    try:
        cur.execute(sql)
        return cur.fetchone()[0]
    except Exception:
        return "unknown"


def print_inventory(cur, host: str) -> dict:
    tables = public_tables(cur)
    counts = table_counts(cur, tables)
    storage_objects = safe_scalar(
        cur, "SELECT count(*) FROM storage.objects WHERE bucket_id = 'setu-documents';"
    )
    auth_users = safe_scalar(cur, "SELECT count(*) FROM auth.users;")
    print(f"Target: {host}")
    print(f"Public application tables: {len(tables)}")
    for table in tables:
        print(f"  public.{table}: {counts[table]} rows")
    print(f"setu-documents storage objects: {storage_objects}")
    print(f"auth.users: {auth_users}")
    return {
        "target": host,
        "tables": counts,
        "storage_objects": storage_objects,
        "auth_users": auth_users,
    }


def delete_storage_objects(cur, config: dict[str, str]) -> int | str:
    try:
        cur.execute("SELECT name FROM storage.objects WHERE bucket_id = 'setu-documents';")
        names = [row[0] for row in cur.fetchall()]
    except Exception:
        return "unknown"
    if not names:
        return 0

    base_url = config.get("SUPABASE_URL") or ""
    secret = config.get("SUPABASE_SECRET_KEY") or ""
    if not base_url or not secret:
        return "unknown"
    if not base_url.startswith("http"):
        base_url = f"https://{base_url}"
    request = urllib.request.Request(
        f"{base_url.rstrip('/')}/storage/v1/object/setu-documents",
        data=json.dumps({"prefixes": names}).encode("utf-8"),
        headers={
            "apikey": secret,
            "Authorization": f"Bearer {secret}",
            "Content-Type": "application/json",
        },
        method="DELETE",
    )
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            if 200 <= response.status < 300:
                return len(names)
            return "unknown"
    except Exception:
        return "unknown"


def write_report(results: dict) -> Path:
    context_dir = Path(__file__).resolve().parents[2] / "context"
    context_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    report_path = context_dir / f"RESET_REPORT.{stamp}.md"
    lines = [
        "# SETU Application Reset Report",
        "",
        f"- Execution timestamp: {results['timestamp']}",
        f"- Target: {results['target']}",
        f"- Backup: {results['backup']}",
        f"- Dropped public tables: {len(results['dropped_tables'])}",
        f"- Storage objects deleted: {results['deleted_storage_objects']}",
        f"- auth.users preserved: {results['auth_users']}",
        f"- Remaining public tables: {len(results['remaining_tables'])}",
        "",
        "## Dropped tables",
        "",
    ]
    lines.extend(f"- `public.{table}`" for table in results["dropped_tables"])
    lines.extend(["", "## Remaining public tables", ""])
    lines.extend(f"- `public.{table}`" for table in results["remaining_tables"])
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    index_lines = [
        "# SETU Reset Reports",
        "",
        f"Latest reset: {results['timestamp']}",
        f"- Report: [{report_path.name}]({report_path.name})",
        f"- Target: {results['target']}",
        f"- Dropped tables: {len(results['dropped_tables'])}",
        f"- Storage objects deleted: {results['deleted_storage_objects']}",
        f"- auth.users preserved: {results['auth_users']}",
        f"- Remaining public tables: {len(results['remaining_tables'])}",
        "",
        "Previous reports are kept as timestamped files in this directory.",
    ]
    (context_dir / "RESET_REPORT.md").write_text("\n".join(index_lines) + "\n", encoding="utf-8")
    return report_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Perform the destructive reset.")
    parser.add_argument("--confirm", default="", help=f"Must equal {CONFIRMATION}.")
    parser.add_argument("--backup", default="", help="Path to a non-empty database dump.")
    parser.add_argument(
        "--allow-production",
        default="",
        help=f"Must equal {PRODUCTION_CONFIRMATION}.",
    )
    parser.add_argument("--env-file", default=None, help="Optional path to the backend .env file.")
    args = parser.parse_args(argv)

    config = resolve_config(Path(args.env_file) if args.env_file else None)
    database_url = config.get("DATABASE_URL", "")
    if not database_url:
        print("ERROR: DATABASE_URL is not available.")
        return 1

    host = masked_host(database_url)
    if not args.apply:
        import psycopg

        with psycopg.connect(database_url) as connection:
            connection.autocommit = True
            with connection.cursor() as cur:
                print_inventory(cur, host)
        print("Read-only inventory. No changes were made.")
        return 0

    require_reset_confirmation(args)

    import psycopg

    results: dict = {
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "target": host,
        "backup": args.backup,
        "dropped_tables": [],
        "deleted_storage_objects": "unknown",
        "auth_users": "unknown",
        "remaining_tables": [],
    }

    with psycopg.connect(database_url) as connection:
        connection.autocommit = True
        with connection.cursor() as cur:
            results["auth_users"] = safe_scalar(cur, "SELECT count(*) FROM auth.users;")
            results["deleted_storage_objects"] = delete_storage_objects(cur, config)
            tables = public_tables(cur)
            for table in tables:
                if table in MANAGED_SCHEMAS:
                    continue
                try:
                    cur.execute(f'DROP TABLE IF EXISTS "public"."{table}" CASCADE;')
                    results["dropped_tables"].append(table)
                except Exception as exc:
                    print(f"Could not drop public.{table}: {exc}")
            results["remaining_tables"] = public_tables(cur)
            results["auth_users_after"] = safe_scalar(cur, "SELECT count(*) FROM auth.users;")

    report_path = write_report(results)
    print(f"Reset report written to {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
