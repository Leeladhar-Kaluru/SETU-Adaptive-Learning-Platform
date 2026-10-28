import uuid
from app.core.config import settings


def test_tests_never_target_supabase():
    assert settings.APP_ENV == "test"
    assert "supabase" not in settings.DATABASE_URL.lower()
    assert "pooler" not in settings.DATABASE_URL.lower()


def test_disposable_database_is_reachable(client):
    rows = client.get("/api/v1/health")
    assert rows.status_code == 200
