import sys
import os
import asyncio
import httpx
from sqlalchemy import text

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.core.config import settings
from app.core.database import SessionLocal

async def main():
    print("=== SUPABASE INVENTORY BEFORE CLEANUP ===")
    
    # 1. DB rows
    db = SessionLocal()
    tables = [
        'teacher_actions',
        'classroom_memberships', 
        'study_events',
        'quiz_attempts',
        'concept_mastery_snapshots',
        'concept_evidence',
        'sync_events',
        'doubts',
        'lesson_versions',
        'generation_jobs',
        'path_lessons',
        'learning_paths',
        'document_chunks',
        'document_pages',
        'documents',
        'classrooms',
        'user_profiles',
        'resources'
    ]
    counts_before = {}
    for t in tables:
        try:
            cnt = db.execute(text(f"SELECT COUNT(*) FROM {t}")).scalar()
            counts_before[t] = cnt
            print(f"Table {t}: {cnt} rows")
        except Exception as e:
            counts_before[t] = str(e)
            print(f"Table {t}: ERROR {e}")
    db.close()

    # 2. Auth Users
    base = settings.SUPABASE_URL.rstrip('/')
    admin_headers = {
        'apikey': settings.SUPABASE_SECRET_KEY,
        'Authorization': f'Bearer {settings.SUPABASE_SECRET_KEY}'
    }
    async with httpx.AsyncClient(timeout=20) as client:
        u_resp = await client.get(f"{base}/auth/v1/admin/users?per_page=100", headers=admin_headers)
        users = []
        if u_resp.status_code == 200:
            users = u_resp.json().get('users', [])
            print(f"\nAuth Users ({len(users)} total):")
            for u in users:
                print(f"  - ID: {u['id']}, Email: {u.get('email', 'no email')}, Created: {u.get('created_at', '')[:19]}")
        else:
            print(f"Auth users list failed: {u_resp.status_code} {u_resp.text}")

        # 3. Storage Objects
        s_resp = await client.post(
            f"{base}/storage/v1/object/list/setu-documents",
            headers={**admin_headers, "Content-Type": "application/json"},
            json={"prefix": "", "limit": 500}
        )
        storage_objects = []
        if s_resp.status_code == 200:
            storage_objects = s_resp.json()
            print(f"\nStorage Objects in 'setu-documents' ({len(storage_objects)} total):")
            for o in storage_objects[:25]:
                print(f"  - Name: {o.get('name')}, Size: {o.get('metadata', {}).get('size', 0)} bytes")
        else:
            print(f"Storage list failed: {s_resp.status_code} {s_resp.text}")

if __name__ == "__main__":
    asyncio.run(main())

