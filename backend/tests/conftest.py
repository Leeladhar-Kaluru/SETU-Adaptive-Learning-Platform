import os
import sys
import uuid

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import text

TEST_DATABASE_URL = os.environ.get("SETU_TEST_DATABASE_URL", "")
if not TEST_DATABASE_URL:
    raise RuntimeError(
        "SETU_TEST_DATABASE_URL is required. Start backend/docker-compose.test.yml "
        "and export the disposable PostgreSQL URL before running pytest."
    )
if "supabase" in TEST_DATABASE_URL.lower() or "pooler" in TEST_DATABASE_URL.lower():
    raise RuntimeError("Refusing to run tests against Supabase or a hosted pooler.")

os.environ["APP_ENV"] = "test"
os.environ["SETU_TEST_AUTH"] = "1"
os.environ["DATABASE_URL"] = TEST_DATABASE_URL
os.environ["SUPABASE_URL"] = ""
os.environ["SUPABASE_SECRET_KEY"] = ""
os.environ["SUPABASE_PUBLISHABLE_KEY"] = ""
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import app.models  # noqa: E402,F401  (registers every table on Base.metadata)
from app.core.database import SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models.base import Base  # noqa: E402

REFERENCE_TABLES = {"alembic_version", "curriculum_boards", "subjects", "languages"}


@pytest.fixture(scope="session", autouse=True)
def migrated_database():
    backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    cfg = Config(os.path.join(backend_dir, "alembic.ini"))
    cfg.set_main_option("script_location", os.path.join(backend_dir, "alembic"))
    command.upgrade(cfg, "head")
    with engine.connect() as conn:
        seeded = conn.execute(text("SELECT COUNT(*) FROM resources")).scalar_one()
        seeded_rights = conn.execute(text("SELECT COUNT(*) FROM resource_rights")).scalar_one()
    if seeded or seeded_rights:
        raise RuntimeError(
            f"Fresh migrations created {seeded} resources and {seeded_rights} rights rows. "
            "Remove catalogue seeds from migrations 001 and 002."
        )
    yield


@pytest.fixture(autouse=True)
def clean_application_tables():
    yield
    table_names = [
        table.name for table in Base.metadata.sorted_tables
        if table.name not in REFERENCE_TABLES
    ]
    if not table_names:
        return
    quoted = ", ".join(f'"{name}"' for name in table_names)
    with engine.begin() as conn:
        conn.execute(text(f"TRUNCATE TABLE {quoted} RESTART IDENTITY CASCADE"))


@pytest.fixture
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


def auth_headers(user_id: uuid.UUID) -> dict[str, str]:
    return {"X-User-Id": str(user_id)}


@pytest.fixture
def student_headers():
    return auth_headers(uuid.uuid4())


def pytest_collection_modifyitems(config, items):
    if os.environ.get("SETU_TEST_LLM_URL"):
        return
    skip = pytest.mark.skip(
        reason="integration test requires SETU_TEST_LLM_URL and a live model server"
    )
    for item in items:
        if "integration" in item.keywords:
            item.add_marker(skip)
