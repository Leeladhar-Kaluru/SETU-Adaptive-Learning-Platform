# SETU Clean Real Product Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove every fabricated user, catalogue entry, lesson, score, and fallback from SETU's production paths so that a fresh account sees honest empty states and every number, lesson, answer, and recommendation is derived from a real uploaded document and real user evidence.

**Architecture:** Work in vertical slices. First make the test suite incapable of touching production and remove seeded data. Then close authorization holes, make ingestion/embedding/generation fail closed, make attempts server-graded, repair the Learn → Solve → Test and offline/doubt loops, and finally make dashboards, teacher evidence, onboarding, and navigation truthful. Each task ships with its own tests and a commit.

**Tech Stack:** React 19, Vite 6, TypeScript, CSS Modules, Dexie 4; FastAPI, SQLAlchemy 2, Alembic, PostgreSQL 16 + pgvector(768), Supabase Auth/Storage; pytest, Playwright.

**Spec:** `SETU_V2_Research_Pack/03_USER_JOURNEYS_AND_FUNCTIONAL_REQUIREMENTS.md`, `05_DOCUMENT_INGESTION_AND_RAG.md`, `06_LEARNING_PATH_AND_LESSON_PACKS.md`, `07_BACKGROUND_GENERATION_JOBS.md`, `08_OFFLINE_FIRST_AND_DOUBT_SYNC.md`, `09_ADAPTIVE_LEARNING_ENGINE.md`, `13_SECURITY_PRIVACY_AND_SUPABASE_RESET.md`, `16_ACCEPTANCE_TESTS_AND_EVALUATION.md`; challenge statement `C:\Users\LEELADHAR\Downloads\Code-Kernel-26-Problem-Statement-Decode.pdf`.

## Global Constraints

- Visible product name is `SETU` everywhere. Never render `SETU V2`, `SETU 2.0`, or another version suffix in UI copy, titles, PWA manifests, onboarding, or generated screens.
- No hardcoded production users, progress, subjects, boards, languages, resource catalogues, classrooms, lessons, quizzes, scores, or analytics. Boards/subjects/languages are reference taxonomy read from the database through APIs, never duplicated as frontend arrays.
- Fixtures and deterministic fakes live only in `backend/tests/` and `frontend/e2e/`. Production code must contain no `_test_fixture`, `sample`, `demo`, or `mock` data path.
- Frontend stays React 19 + Vite + TypeScript + CSS Modules; no Tailwind v4, no shadcn.
- Backend stays FastAPI + Supabase PostgreSQL/Auth/Storage; embeddings are 768-dimensional pgvector values.
- Offline data lives in IndexedDB (Dexie), is scoped to the signed-in user, and sync is authenticated and idempotent.
- Never print, log, or commit secrets. Never expose the Supabase service-role key to the browser.
- Never run a broad database drop/reset. Cleanup is scoped to explicitly named users/rows and requires an inventory and explicit confirmation. Preserve `auth`, `storage`, `vault`, `realtime`, and `extensions`.
- Every visible button and navigation item must either perform its labelled action or be disabled with a visible reason.
- Update `STATUS_REPORT.md` each session with exact commands, outputs, blockers, and next steps.

## Review Focus

1. **A brand-new account opens Home/Dashboard before uploading anything.** It must show zero minutes, zero attempts, no mastery bands, no resources, no "Class 9"/"25 minutes" defaults, and an action to upload or finish onboarding. Pinned by Tasks 2, 13, and 15.
2. **A signed-in student calls a teacher endpoint, opens another user's lesson, or requests another user's extracted diagram.** Every one must return `403`/`404` without leaking existence. Pinned by Task 4.
3. **The embedding or chat provider is down during ingestion or lesson generation.** The document/lesson must fail with a truthful retryable error; no zero vectors, partial chunks, or fabricated lesson may be marked ready. Pinned by Tasks 5, 6, and 7.
4. **A student answers offline, reconnects, and syncs twice.** The attempt must be graded by the server once, appear once in evidence, and the second sync must be idempotent. Pinned by Tasks 9 and 11.
5. **The model returns a lesson with a missing citation or empty answer key.** Validation must reject it; the lesson must not appear as ready and no `Question` rows may be published. Pinned by Task 7.

---

### Task 1: Isolated Test Database and Fail-Closed Harness

**Files:**
- Create: `backend/docker-compose.test.yml`
- Create: `backend/tests/__init__.py` (empty; makes `from tests.conftest import auth_headers` resolve to the same module pytest loaded)
- Modify: `backend/tests/conftest.py`
- Modify: `backend/pytest.ini`
- Create: `backend/tests/test_harness_guard.py`
- Modify: `backend/tests/test_rag_evaluation.py` (module marker only)
- Modify: `backend/tests/test_e2e_vertical_slice.py` (module marker only)
- Modify: `backend/tests/test_auth_and_profiles.py` (remove live signup, synthetic tokens, and seeded-catalogue assumptions)
- Modify: `backend/tests/test_multi_user_evidence_matrix.py` (temporary skip until Task 14 rewrites it)
- Modify: `backend/tests/test_idempotent_sync.py` (temporary skip until Task 12 makes provider failures retryable)

**Interfaces:**
- Consumes: `app.core.config.settings`, `app.core.database.engine`, `app.models.base.Base`.
- Produces: `SETU_TEST_DATABASE_URL` (required), `client`, `db`, and `auth_headers(user_id: uuid.UUID) -> dict[str, str]` pytest fixtures. Every test runs against a disposable PostgreSQL database.

- [ ] **Step 1: Write the failing guard test**

```python
# backend/tests/test_harness_guard.py
import uuid
from app.core.config import settings


def test_tests_never_target_supabase():
    assert settings.APP_ENV == "test"
    assert "supabase" not in settings.DATABASE_URL.lower()
    assert "pooler" not in settings.DATABASE_URL.lower()


def test_disposable_database_is_reachable(client):
    rows = client.get("/api/v1/health")
    assert rows.status_code == 200
```

- [ ] **Step 2: Run it and confirm the harness refuses to start**

Run from `backend/`:

```powershell
.\.venv\Scripts\python -m pytest tests/test_harness_guard.py -q
```

Expected: FAIL/ERROR because `SETU_TEST_DATABASE_URL` is not set and `conftest.py` has no guard. This is the desired fail-closed behavior.

- [ ] **Step 3: Create the disposable database**

```yaml
# backend/docker-compose.test.yml
services:
  postgres-test:
    image: pgvector/pgvector:pg16
    environment:
      POSTGRES_USER: setu
      POSTGRES_PASSWORD: setu_test
      POSTGRES_DB: setu_test
    ports:
      - "55432:5432"
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U setu -d setu_test"]
      interval: 2s
      timeout: 2s
      retries: 30
    tmpfs:
      - /var/lib/postgresql/data
```

Start it from `backend/`:

```powershell
docker compose -f docker-compose.test.yml up -d
```

Expected: container is healthy on `127.0.0.1:55432`.

- [ ] **Step 4: Replace `conftest.py` with the fail-closed harness**

```python
# backend/tests/conftest.py
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
```

- [ ] **Step 5: Mark the live-model tests and add markers**

Add `pytestmark = pytest.mark.integration` at module level in `backend/tests/test_rag_evaluation.py` and `backend/tests/test_e2e_vertical_slice.py`. Add to `backend/pytest.ini`:

```ini
markers =
    integration: requires live LLM or storage services
```

Then rewrite `backend/tests/test_auth_and_profiles.py` so it does not call Supabase, use synthetic bearer tokens, or assume seeded catalogue rows:

- Use the `client` and `db` fixtures instead of a module-level `TestClient(app)`.
- Replace the live signup test with a real profile row inserted through `db` (with `grade=9`, `board_id="board-cbse"`, and `preferred_language="en-IN"`), then exercise `GET /api/v1/profile` and `PUT /api/v1/profile` with `X-User-Id`.
- Insert a teacher `UserProfile` and a student `UserProfile`; replace both `test-token-` headers with `X-User-Id`; use `subjectScope: "subject-science"` so the classroom remains valid after Task 15.
- Replace the catalogue-count assertions with rows the test inserts itself: one `ResourceSource`, two `Resource` rows at grades 6 and 10, and their explicit `ResourceRight` rows. Assert the grade filter returns only the inserted grade. Never assert that a seeded catalogue exists.
- Add `pytestmark = pytest.mark.skip(reason="attempt/recommendation contracts are rewritten in Task 14")` at module level in `backend/tests/test_multi_user_evidence_matrix.py`. Task 14 removes this marker after rewriting the file.
- Add `pytestmark = pytest.mark.skip(reason="provider failures become retryable in Task 12")` at module level in `backend/tests/test_idempotent_sync.py`. Task 12 removes this marker after implementing retryable failures.

- [ ] **Step 6: Run the guard and the existing unit suite**

```powershell
$env:SETU_TEST_DATABASE_URL="postgresql://setu:setu_test@127.0.0.1:55432/setu_test"
.\.venv\Scripts\python -m pytest tests -q
```

Expected: `test_harness_guard.py` passes; integration tests are skipped; `test_multi_user_evidence_matrix.py` and `test_idempotent_sync.py` are skipped only until Tasks 14 and 12 rewrite them; no test writes to the Supabase database. A suite that previously failed because `.env` pointed at production now fails only for real code defects. If any other test still requires a live model, storage bucket, or hosted auth, mark it `integration` and make it skip without `SETU_TEST_LLM_URL` rather than letting it hit production.

- [ ] **Step 7: Commit**

```bash
git add backend/docker-compose.test.yml backend/tests/__init__.py backend/tests/conftest.py backend/pytest.ini backend/tests/test_harness_guard.py backend/tests/test_rag_evaluation.py backend/tests/test_e2e_vertical_slice.py backend/tests/test_auth_and_profiles.py backend/tests/test_multi_user_evidence_matrix.py backend/tests/test_idempotent_sync.py
git commit -m "test: isolate backend tests from production database"
```

---

### Task 2: Remove Seeded Catalogue and Academic Profile Defaults

**Files:**
- Create: `backend/alembic/versions/006_remove_seeded_catalogue_and_profile_defaults.py`
- Modify: `backend/alembic/versions/001_initial_setu_schema.py` (remove resource seed block only)
- Modify: `backend/alembic/versions/002_user_profiles_and_curriculum_catalog.py` (remove resource seed block only)
- Modify: `backend/app/models/profiles.py`
- Modify: `backend/app/models/curriculum.py` only if a default remains
- Modify: `backend/app/api/v1/catalogue.py` (no fabricated display fallbacks)
- Modify: `backend/tests/conftest.py` (assert a fresh migration seeds no catalogue rows)
- Create: `backend/tests/test_catalogue_and_profile_defaults.py`

**Interfaces:**
- Consumes: Alembic head `005`; `Resource`, `ResourceRight`, `UserProfile`.
- Produces: migration `006`; a fresh `001`→`006` install contains no resource catalogue rows; `GET /api/v1/catalogue/resources` returns `[]` until a real resource is inserted; new `UserProfile` rows have `grade is None`, `board_id is None`, `daily_goal_minutes is None`, `preferred_language is None`.

- [ ] **Step 1: Write the failing tests**

```python
# backend/tests/test_catalogue_and_profile_defaults.py
import uuid
from app.models.profiles import UserProfile


def test_new_profile_has_no_academic_defaults(db):
    profile = UserProfile(
        id=uuid.uuid4(),
        email="fresh@example.com",
        display_name="Fresh Learner",
    )
    db.add(profile)
    db.commit()
    db.refresh(profile)
    assert profile.grade is None
    assert profile.board_id is None
    assert profile.daily_goal_minutes is None
    assert profile.preferred_language is None


def test_catalogue_resources_are_empty_until_real_data_is_added(client):
    assert client.get("/api/v1/catalogue/resources").json() == []


def test_reference_taxonomy_is_still_available(client):
    boards = client.get("/api/v1/catalogue/boards").json()
    subjects = client.get("/api/v1/catalogue/subjects").json()
    assert any(board["id"] == "board-cbse" for board in boards)
    assert any(subject["id"] == "subject-science" for subject in subjects)
```

- [ ] **Step 2: Run the tests and confirm they fail**

```powershell
.\.venv\Scripts\python -m pytest tests/test_catalogue_and_profile_defaults.py -q
```

Expected: FAIL because the database still contains 26 seeded resources and the profile defaults are `9`/`board-cbse`/`25`.

- [ ] **Step 3: Write migration `006` for databases that already ran `001`–`005`**

Use the exact 26 IDs from `001_initial_setu_schema.py` and `002_user_profiles_and_curriculum_catalog.py`:

```python
# backend/alembic/versions/006_remove_seeded_catalogue_and_profile_defaults.py
"""remove seeded catalogue and academic profile defaults"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "006"
down_revision: Union[str, None] = "005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

SEEDED_RESOURCE_IDS = (
    "res-ncert-sci-9", "res-ncert-math-9", "res-ncert-sci-10",
    "res-cbse-6-sci-food", "res-cbse-6-math-num", "res-cbse-6-soc-hist",
    "res-cbse-6-eng-sun", "res-cbse-6-hin-vas",
    "res-cbse-7-sci-nutri", "res-cbse-7-math-frac", "res-cbse-7-soc-env",
    "res-cbse-7-eng-comb",
    "res-cbse-8-sci-crop", "res-cbse-8-math-linear", "res-cbse-8-soc-res",
    "res-cbse-8-eng-dew",
    "res-cbse-9-sci-matter", "res-cbse-9-math-geom", "res-cbse-9-soc-dem",
    "res-cbse-9-soc-eco", "res-cbse-9-it-comp",
    "res-cbse-10-sci-light", "res-cbse-10-math-quad", "res-cbse-10-math-trig",
    "res-cbse-10-soc-india", "res-cbse-10-it-ai",
)


def upgrade() -> None:
    ids = ", ".join(f"'{resource_id}'" for resource_id in SEEDED_RESOURCE_IDS)
    op.execute(f"UPDATE documents SET resource_id = NULL WHERE resource_id IN ({ids})")
    op.execute(f"DELETE FROM resource_rights WHERE resource_id IN ({ids})")
    op.execute(f"DELETE FROM resources WHERE id IN ({ids})")
    op.execute(
        "DELETE FROM resource_sources WHERE id = 'ncert-portal' "
        "AND NOT EXISTS (SELECT 1 FROM resources WHERE source_id = 'ncert-portal')"
    )
    op.alter_column("user_profiles", "board_id", server_default=None)
    op.alter_column(
        "user_profiles", "grade", existing_type=sa.Integer(),
        nullable=True, server_default=None,
    )
    op.alter_column(
        "user_profiles", "daily_goal_minutes", existing_type=sa.Integer(),
        nullable=True, server_default=None,
    )
    op.alter_column(
        "user_profiles", "preferred_language", existing_type=sa.String(20),
        nullable=True, server_default=None,
    )


def downgrade() -> None:
    op.alter_column("user_profiles", "board_id", server_default="board-cbse")
    op.execute("UPDATE user_profiles SET grade = 9 WHERE grade IS NULL")
    op.execute("UPDATE user_profiles SET daily_goal_minutes = 25 WHERE daily_goal_minutes IS NULL")
    op.execute("UPDATE user_profiles SET preferred_language = 'en-IN' WHERE preferred_language IS NULL")
    op.alter_column(
        "user_profiles", "grade", existing_type=sa.Integer(),
        nullable=False, server_default="9",
    )
    op.alter_column(
        "user_profiles", "daily_goal_minutes", existing_type=sa.Integer(),
        nullable=False, server_default="25",
    )
    op.alter_column(
        "user_profiles", "preferred_language", existing_type=sa.String(20),
        nullable=False, server_default="en-IN",
    )
```

- [ ] **Step 4: Remove the catalogue seed blocks from migrations `001` and `002`**

Migration `006` repairs existing databases, but a fresh install must never insert the fabricated catalogue in the first place. Edit the two historical migrations without changing their revision IDs:

In `001_initial_setu_schema.py`, delete the entire `op.execute(...)` block that inserts into `resources` and `resource_rights`. Also delete the single `INSERT INTO resource_sources ... ('ncert-portal', ...)` block if no retained row references it. Keep the `curriculum_boards`, `subjects`, and `languages` inserts unchanged; they are reference taxonomy, not a resource catalogue.

In `002_user_profiles_and_curriculum_catalog.py`, delete the `catalog_resources = [...]` list, the `for` loop that inserts resources and rights, and any now-unused `text`/`bindparams` imports. Keep the `subject-it` taxonomy insert and the profile column changes. Migration `006` still removes the 26 rows from databases that already applied the old versions.

Then add a harness assertion to `backend/tests/conftest.py` so a future seed cannot slip back in. Replace the existing `yield` in `migrated_database` with:

```python
    with engine.connect() as conn:
        seeded = conn.execute(text("SELECT COUNT(*) FROM resources")).scalar_one()
        seeded_rights = conn.execute(text("SELECT COUNT(*) FROM resource_rights")).scalar_one()
    if seeded or seeded_rights:
        raise RuntimeError(
            f"Fresh migrations created {seeded} resources and {seeded_rights} rights rows. "
            "Remove catalogue seeds from migrations 001 and 002."
        )
    yield
```

This runs once per test session, before the per-test truncation, so the empty-catalogue test cannot pass merely because a previous test cleaned the tables.

- [ ] **Step 5: Remove model defaults and fabricated catalogue names**

In `backend/app/models/profiles.py`, change `preferred_language`, `board_id`, `grade`, and `daily_goal_minutes` to have no `default=`. Keep `role` defaulting to `"student"` because signup submits a role.

In `backend/app/models/curriculum.py`, make unconfigured resources fail closed: change `Resource.verification_status` to default `"unverified"` and change every `ResourceRight.can_*` permission to default `False`. A resource that has not been explicitly reviewed must grant no download, storage, processing, embedding, offline-cache, or redistribution rights.

In `backend/app/api/v1/catalogue.py`, replace the two fallback expressions with truthful labels:

```python
subj_name = subjects_map.get(r.subject_id) or "Unknown subject"
board_name = boards_map.get(r.board_id) or "Unknown board"
```

- [ ] **Step 6: Run the migration and tests**

```powershell
$env:SETU_TEST_DATABASE_URL="postgresql://setu:setu_test@127.0.0.1:55432/setu_test"
$env:DATABASE_URL=$env:SETU_TEST_DATABASE_URL
.\.venv\Scripts\python -m alembic -c alembic.ini upgrade head
.\.venv\Scripts\python -m pytest tests/test_catalogue_and_profile_defaults.py -q
```

Expected: PASS against the disposable database; `resources` and `resource_rights` contain zero seeded rows; taxonomy tables still return `board-cbse` and `subject-science`. Do not run this migration against Supabase until the cleanup in Task 3 has been confirmed.

- [ ] **Step 7: Commit**

```bash
git add backend/alembic/versions/001_initial_setu_schema.py backend/alembic/versions/002_user_profiles_and_curriculum_catalog.py backend/alembic/versions/006_remove_seeded_catalogue_and_profile_defaults.py backend/app/models/profiles.py backend/app/models/curriculum.py backend/app/api/v1/catalogue.py backend/tests/conftest.py backend/tests/test_catalogue_and_profile_defaults.py
git commit -m "chore: remove seeded catalogue and academic defaults"
```

---

### Task 3: Scoped Demo-Data Cleanup with Inventory and Confirmation Gate

**Files:**
- Create: `backend/scripts/cleanup_demo_data.py`
- Create: `backend/tests/test_cleanup_demo_data.py`
- Modify: `context/SUPABASE_CLEANUP_MANIFEST.md`

**Interfaces:**
- Consumes: `Session`, table models, `storage_service.delete_file(bucket, path) -> bool`.
- Produces: `inventory(db: Session, *, list_storage_objects=None) -> dict`, `cleanup(db, *, delete_user_ids: set[uuid.UUID], preserve_user_ids: set[uuid.UUID], apply: bool, delete_storage_object=None) -> dict`, and CLI `python scripts/cleanup_demo_data.py --inventory` / `--apply --delete-user-id <uuid> --preserve-user-id <uuid> --confirm APPLY-CLEANUP`.

- [ ] **Step 1: Write the failing cleanup test**

```python
# backend/tests/test_cleanup_demo_data.py
import uuid
from app.models.documents import Document
from app.models.profiles import UserProfile
from scripts.cleanup_demo_data import cleanup, inventory


def _profile(db, email):
    profile = UserProfile(id=uuid.uuid4(), email=email, display_name=email.split("@")[0])
    db.add(profile)
    db.flush()
    return profile


def test_cleanup_deletes_only_explicitly_named_users(db):
    real = _profile(db, "real@gmail.com")
    demo = _profile(db, "demo@example.com")
    db.add(Document(
        owner_id=real.id, original_filename="real.pdf", storage_key=f"documents/{real.id}/real.pdf",
        mime_type="application/pdf", size_bytes=10, status="ready",
    ))
    db.add(Document(
        owner_id=demo.id, original_filename="demo.pdf", storage_key=f"documents/{demo.id}/demo.pdf",
        mime_type="application/pdf", size_bytes=10, status="ready",
    ))
    db.commit()

    before = inventory(db)
    assert before["profiles"] == 2

    report = cleanup(
        db,
        delete_user_ids={demo.id},
        preserve_user_ids={real.id},
        apply=True,
        delete_storage_object=lambda bucket, path: True,
    )

    assert report["deleted_users"] == 1
    assert db.get(UserProfile, demo.id) is None
    assert db.get(UserProfile, real.id) is not None
    assert db.query(Document).filter(Document.owner_id == real.id).count() == 1
    assert db.query(Document).filter(Document.owner_id == demo.id).count() == 0


def test_cleanup_refuses_to_delete_a_preserved_user(db):
    real = _profile(db, "real@gmail.com")
    db.commit()
    try:
        cleanup(
            db,
            delete_user_ids={real.id},
            preserve_user_ids={real.id},
            apply=True,
        )
    except ValueError as exc:
        assert "preserved" in str(exc).lower()
    else:
        raise AssertionError("cleanup must refuse to delete a preserved user")
```

- [ ] **Step 2: Run and confirm failure**

```powershell
.\.venv\Scripts\python -m pytest tests/test_cleanup_demo_data.py -q
```

Expected: FAIL because `scripts.cleanup_demo_data` does not exist.

- [ ] **Step 3: Implement the inventory and scoped cleanup**

`inventory` must return counts only, never secrets:

```python
{
    "profiles": 9,
    "profiles_by_domain": {"example.com": 8, "gmail.com": 1},
    "documents": 13,
    "document_pages": 628,
    "document_chunks": 1086,
    "learning_paths": 1,
    "path_lessons": 24,
    "lesson_versions": 17,
    "quiz_attempts": 0,
    "concept_evidence": 0,
    "doubts": 15,
    "classrooms": 8,
    "classroom_memberships": 8,
    "teacher_actions": 0,
    "study_events": 6,
    "generation_jobs": 24,
    "resources": 26,
    "storage_objects": 13,
    "users": [
        {"id": "...", "email": "masked", "domain": "example.com", "is_test_domain": True}
    ],
}
```

If `list_storage_objects` is not supplied, or the storage query fails, return `"storage_objects": None` instead of inventing a count. The tests call `inventory(db)` without a storage probe.

`cleanup` must:

1. Raise `ValueError` if `delete_user_ids & preserve_user_ids`.
2. Raise `ValueError` if `apply` is true and `delete_user_ids` is empty.
3. Collect `documents` owned by deleted users and call `delete_storage_object("setu-documents", storage_key)` before deleting rows. A failed storage delete is recorded and does not abort the database cleanup.
4. Delete in FK-safe order: `teacher_actions`, `classroom_memberships`, `classrooms`, `sync_events`, `doubts`, `concept_evidence`, `concept_mastery_snapshots`, `quiz_attempts`, `study_events`, `generation_jobs`, `learning_paths` (cascades path lessons/versions/questions), `documents` (cascades pages/chunks), `user_profiles`.
5. Clear `documents.resource_id` for any document still pointing at a seeded resource, then delete the 26 seeded resource IDs and their rights as a safety net, even though migration `006` already did it.
6. Return counts by table plus `deleted_users`, `preserved_users`, `storage_deleted`, `storage_failed`.
7. Never delete `auth.users` unless `--delete-auth-users` is explicitly passed; that path calls the Supabase Admin API per user and logs only user IDs.

- [ ] **Step 4: Implement the CLI confirmation gate**

```python
parser.add_argument("--inventory", action="store_true")
parser.add_argument("--apply", action="store_true")
parser.add_argument("--delete-user-id", action="append", default=[])
parser.add_argument("--preserve-user-id", action="append", default=[])
parser.add_argument("--delete-auth-users", action="store_true")
parser.add_argument("--confirm", default="")
```

Refuse `--apply` unless `--confirm APPLY-CLEANUP` and at least one `--delete-user-id` and one `--preserve-user-id` are present. Print the inventory, then the exact IDs and masked emails that will be deleted. Write the result to `context/CLEANUP_REPORT.md`; never print `DATABASE_URL` or keys.

- [ ] **Step 5: Run the cleanup tests and the production inventory only**

```powershell
.\.venv\Scripts\python -m pytest tests/test_cleanup_demo_data.py -q
cd ..
.\.venv\Scripts\python backend\scripts\cleanup_demo_data.py --inventory
```

Expected: tests PASS. Inventory reports the current 9 profiles, 13 documents, 8 classrooms, and 26 resources. **Do not run `--apply` until the user confirms which user IDs are demo accounts and which one is the real `gmail.com` account.** This is a blocking human gate, not a code task.

- [ ] **Step 6: Commit**

```bash
git add backend/scripts/cleanup_demo_data.py backend/tests/test_cleanup_demo_data.py context/SUPABASE_CLEANUP_MANIFEST.md
git commit -m "chore: add scoped demo-data cleanup inventory"
```

---

### Task 4: Close Trust Boundaries and Stop Fabricated Identity

**Files:**
- Modify: `backend/app/core/security.py`
- Modify: `backend/app/core/config.py` (add `SETU_TEST_AUTH`)
- Create: `backend/app/services/profiles.py`
- Modify: `backend/app/api/v1/auth.py`
- Modify: `backend/app/api/v1/learning_paths.py:225-257`
- Modify: `backend/app/api/v1/documents.py:252-265`
- Modify: `backend/app/api/v1/teacher.py:18-25,47-70`
- Modify: `backend/app/api/v1/profile.py` (remove role from update contract)
- Modify: `backend/tests/test_e2e_vertical_slice.py` (replace the synthetic bearer token with `X-User-Id`)
- Create: `backend/tests/test_authorization.py`
- Create: `backend/tests/test_profile_provisioning.py`

**Interfaces:**
- Consumes: `get_db`, `UserProfile`, `LearningPath`, `PathLesson`, `Document`.
- Produces: `get_current_teacher_id` that returns `403` for non-teachers; `ensure_profile_from_auth(db, user_id, email, display_name, role="student", grade=None, board_id=None, preferred_language=None) -> UserProfile`; `X-User-Id` accepted only when `APP_ENV == "test"` and `SETU_TEST_AUTH` is true; no synthetic `test-token-` or `setu-token-` auth.

- [ ] **Step 1: Write the failing authorization tests**

```python
# backend/tests/test_authorization.py
import uuid
from pathlib import Path

from app.models.documents import Document
from app.models.learning import LearningPath, PathLesson, LessonVersion
from app.models.profiles import UserProfile


def _profile(db, role="student"):
    user_id = uuid.uuid4()
    db.add(UserProfile(
        id=user_id, email=f"{role}-{user_id.hex[:6]}@example.com",
        display_name=f"{role.title()} User", role=role,
    ))
    db.commit()
    return user_id


def test_student_cannot_call_teacher_endpoint(client, db):
    student_id = _profile(db, "student")
    response = client.get("/api/v1/teacher/classrooms", headers={"X-User-Id": str(student_id)})
    assert response.status_code == 403


def test_teacher_can_create_a_real_join_code(client, db):
    teacher_id = _profile(db, "teacher")
    response = client.post(
        "/api/v1/teacher/classrooms",
        headers={"X-User-Id": str(teacher_id)},
        json={"name": "Morning Science", "grade": 9, "boardId": "board-cbse", "subjectScope": "subject-science"},
    )
    assert response.status_code == 200
    code = response.json()["joinCode"]
    assert code != "SETU-JOIN"
    assert 5 <= len(code) <= 6


def test_lesson_is_not_readable_by_another_user(client, db, tmp_path):
    owner_id = _profile(db)
    other_id = _profile(db)
    path = LearningPath(
        owner_id=owner_id, grade=9, subject_id="subject-science",
        outline_json={"title": "Test path"}, status="active",
    )
    db.add(path)
    db.flush()
    lesson = PathLesson(path_id=path.id, lesson_key="lesson_1", title="Cells", sequence=1, status="ready")
    db.add(lesson)
    db.flush()
    db.add(LessonVersion(
        path_lesson_id=lesson.id, version_number=1,
        lesson_package_json={"title": "Cells"}, validation_status="ready",
    ))
    db.commit()

    owner_response = client.get(
        f"/api/v1/learning-paths/lessons/{lesson.id}", headers={"X-User-Id": str(owner_id)}
    )
    other_response = client.get(
        f"/api/v1/learning-paths/lessons/{lesson.id}", headers={"X-User-Id": str(other_id)}
    )
    assert owner_response.status_code == 200
    assert other_response.status_code == 404


def test_diagram_requires_document_owner(client, db):
    owner_id = _profile(db)
    other_id = _profile(db)
    doc = Document(
        owner_id=owner_id, original_filename="book.pdf", storage_key="documents/book.pdf",
        mime_type="application/pdf", size_bytes=10, status="awaiting_review",
    )
    db.add(doc)
    db.commit()

    diagram_dir = Path(__file__).resolve().parents[1] / "diagrams" / str(doc.id)
    diagram_dir.mkdir(parents=True, exist_ok=True)
    diagram = diagram_dir / "page_1_d0.png"
    diagram.write_bytes(b"\x89PNG\r\n\x1a\n")

    assert client.get(
        f"/api/v1/documents/{doc.id}/diagrams/page_1_d0.png",
        headers={"X-User-Id": str(other_id)},
    ).status_code == 404
    assert client.get(
        f"/api/v1/documents/{doc.id}/diagrams/page_1_d0.png",
        headers={"X-User-Id": str(owner_id)},
    ).status_code == 200
    diagram.unlink()
    diagram_dir.rmdir()
```

- [ ] **Step 2: Write the failing profile-provisioning tests**

```python
# backend/tests/test_profile_provisioning.py
import uuid

from app.models.profiles import UserProfile
from app.services.profiles import ensure_profile_from_auth


def test_profile_from_auth_has_no_invented_academic_context(db):
    user_id = uuid.uuid4()
    profile = ensure_profile_from_auth(
        db, user_id, email="new@example.com", display_name="New Learner"
    )
    db.commit()
    db.refresh(profile)
    assert profile.display_name == "New Learner"
    assert profile.grade is None
    assert profile.board_id is None
    assert profile.daily_goal_minutes is None


def test_profile_role_cannot_be_self_escalated(client, db):
    user_id = uuid.uuid4()
    ensure_profile_from_auth(db, user_id, email="student@example.com", display_name="Student")
    response = client.put(
        "/api/v1/profile",
        headers={"X-User-Id": str(user_id)},
        json={"role": "teacher"},
    )
    assert response.status_code == 200
    assert response.json()["profile"]["role"] == "student"
    assert db.get(UserProfile, user_id).role == "student"


def test_synthetic_test_token_is_rejected(client):
    response = client.get(
        "/api/v1/profile",
        headers={"Authorization": "Bearer test-token-00000000-0000-0000-0000-000000000000"},
    )
    assert response.status_code == 401


def test_x_user_id_can_be_disabled(client, monkeypatch):
    from app.core.config import settings
    monkeypatch.setattr(settings, "SETU_TEST_AUTH", False)
    response = client.get(
        "/api/v1/profile",
        headers={"X-User-Id": str(uuid.uuid4())},
    )
    assert response.status_code == 401
```

- [ ] **Step 3: Run the tests and confirm they fail**

```powershell
.\.venv\Scripts\python -m pytest tests/test_authorization.py tests/test_profile_provisioning.py -q
```

Expected: FAIL — students can call teacher endpoints, cross-user lessons/diagrams are readable, `test-token-` is accepted, and profiles are created with `grade=9`.

- [ ] **Step 4: Implement the security boundary**

Add to `backend/app/core/config.py`:

```python
SETU_TEST_AUTH: bool = False
```

In `backend/app/core/security.py`:

- Delete the `token.startswith("test-token-")` branch entirely.
- Accept `x_user_id` only when `settings.APP_ENV == "test" and settings.SETU_TEST_AUTH`.
- Replace `get_current_teacher_id` with:

```python
async def get_current_teacher_id(
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> uuid.UUID:
    profile = db.query(UserProfile).filter(UserProfile.id == user_id).first()
    if not profile or profile.role not in ("teacher", "admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="A teacher account is required for this action.",
        )
    return user_id
```

Import `UserProfile` at the top. Keep `verify_supabase_token` unchanged for real Supabase tokens.

Create `backend/app/services/profiles.py`:

```python
def ensure_profile_from_auth(
    db: Session,
    user_id: uuid.UUID,
    *,
    email: str | None,
    display_name: str,
    role: str = "student",
    grade: int | None = None,
    board_id: str | None = None,
    preferred_language: str | None = None,
) -> UserProfile:
    profile = db.query(UserProfile).filter(UserProfile.id == user_id).first()
    if profile:
        return profile
    profile = UserProfile(
        id=user_id, email=email, display_name=display_name.strip()[:150],
        role=role if role in ("student", "teacher", "parent", "admin") else "student",
        grade=grade, board_id=board_id, preferred_language=preferred_language,
        onboarding_completed=False, tour_completed=False,
    )
    db.add(profile)
    db.commit()
    db.refresh(profile)
    return profile
```

In `auth.py`:

- `SignupRequest.grade: Optional[int] = None`, `boardId: Optional[str] = None`, `preferredLanguage: Optional[str] = None`.
- Replace profile upsert with `ensure_profile_from_auth(...)`, passing only the real signup values. Remove `or 9`, `or "board-cbse"`, and `or "en-IN"`.
- If no access token was issued, raise `HTTPException(503, "Authentication token was not issued. Try signing in again.")`; never synthesize one.
- In `login`, if no profile exists, create one with `ensure_profile_from_auth(db, user_uuid, email=req.email, display_name=req.email.split("@")[0])`; no grade/board.
- In `get_me`, if no profile exists, raise `HTTPException(404, "Profile not found. Complete signup or onboarding.")`; do not create a "Learner" profile.
- In `update_profile` (still in `profile.py`), Task 13 removes the fallback; for now leave it untouched. Remove `role` from `ProfileUpdateRequest` entirely so a student cannot self-escalate by calling `PUT /profile`. The role is set only at signup and then by an administrator.
- In `profile.py` `get_profile` and `get_student_dashboard`, Task 13 removes the fallback.

Update `backend/tests/test_e2e_vertical_slice.py` so its two sync calls use `headers={"X-User-Id": str(owner_uuid)}` instead of `Authorization: Bearer test-token-...`. Task 4 deletes the synthetic-token branch, and the integration test must still authenticate through the same test-only `X-User-Id` gate as every other test.

- [ ] **Step 5: Enforce ownership and remove fabricated join codes**

In `learning_paths.py`, replace the lesson lookup with:

```python
lesson = (
    db.query(PathLesson)
    .join(LearningPath, LearningPath.id == PathLesson.path_id)
    .filter(PathLesson.id == lesson_uuid, LearningPath.owner_id == owner_id)
    .first()
)
```

Apply the same `LearningPath.owner_id == owner_id` filter to the `lesson_key` lookup. Add `"lessonVersionId": str(version.id)` to the returned package dictionary (without mutating the stored JSON):

```python
package = dict(version.lesson_package_json)
package["lessonVersionId"] = str(version.id)
return package
```

In `documents.py`, add `owner_id: uuid.UUID = Depends(get_current_user_id)` and `db: Session = Depends(get_db)` to `get_extracted_diagram`, then verify:

```python
doc = db.query(Document).filter(
    Document.id == document_id, Document.owner_id == owner_id
).first()
if not doc:
    raise HTTPException(status_code=404, detail="Diagram not found")
```

In `teacher.py`, delete `_normalize_code`; use `generate_join_code` and raise `HTTPException(503, "Could not allocate a unique classroom code. Try again.")` if all attempts collide. Remove `c.join_code or "SETU-JOIN"`; if a legacy row has no code, return `None` and let the UI show "Code unavailable" with a retry action.

- [ ] **Step 6: Run the tests**

```powershell
.\.venv\Scripts\python -m pytest tests/test_authorization.py tests/test_profile_provisioning.py -q
```

Expected: PASS. A student receives `403`, cross-user lessons/diagrams receive `404`, `test-token-` receives `401`, and a new profile has no grade/board/pace.

- [ ] **Step 7: Commit**

```bash
git add backend/app/core/config.py backend/app/core/security.py backend/app/services/profiles.py backend/app/api/v1/auth.py backend/app/api/v1/profile.py backend/app/api/v1/learning_paths.py backend/app/api/v1/documents.py backend/app/api/v1/teacher.py backend/tests/test_authorization.py backend/tests/test_profile_provisioning.py backend/tests/test_e2e_vertical_slice.py
git commit -m "fix: enforce teacher, lesson, and diagram ownership"
```

---

### Task 5: Make Embeddings and Retrieval Fail Closed

**Files:**
- Modify: `backend/app/core/ai_provider.py`
- Modify: `backend/app/services/retrieval.py`
- Create: `backend/tests/test_ai_provider_truth.py`
- Create: `backend/tests/test_retrieval_truth.py`

**Interfaces:**
- Consumes: `settings.EMBEDDING_MODEL`, `settings.EMBEDDING_DIMENSION`, `DocumentChunk`.
- Produces: `EmbeddingUnavailableError(RuntimeError)`; `get_embedding(text)` and `get_embeddings_batch(texts)` raise on empty input, provider failure, count mismatch, or dimension mismatch. `hybrid_search` returns only chunks with a valid embedding and the configured model/dimension.

- [ ] **Step 1: Write the failing provider tests**

```python
# backend/tests/test_ai_provider_truth.py
import httpx
import pytest

from app.core.ai_provider import ai_provider


@pytest.mark.asyncio
async def test_empty_text_is_rejected():
    with pytest.raises(ValueError, match="empty"):
        await ai_provider.get_embedding("   ")


@pytest.mark.asyncio
async def test_wrong_dimension_is_rejected(monkeypatch):
    class FakeResponse:
        status_code = 200
        def json(self):
            return {"data": [{"index": 0, "embedding": [0.1] * 12}]}

    async def fake_post(self, url, json):
        return FakeResponse()

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)
    with pytest.raises(ValueError, match="dimension"):
        await ai_provider.get_embedding("real text")


@pytest.mark.asyncio
async def test_batch_count_mismatch_is_rejected(monkeypatch):
    class FakeResponse:
        status_code = 200
        def json(self):
            return {"data": [{"index": 0, "embedding": [0.1] * 768}]}

    async def fake_post(self, url, json):
        return FakeResponse()

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)
    with pytest.raises(ValueError, match="count"):
        await ai_provider.get_embeddings_batch(["one", "two"])
```

- [ ] **Step 2: Write the failing retrieval test**

```python
# backend/tests/test_retrieval_truth.py
import uuid
import pytest

from app.models.documents import Document, DocumentChunk
from app.services import retrieval as retrieval_module
from app.services.retrieval import retrieval_service


@pytest.mark.asyncio
async def test_retrieval_excludes_unembedded_and_foreign_chunks(db, monkeypatch):
    owner_id = uuid.uuid4()
    other_id = uuid.uuid4()
    doc = Document(
        owner_id=owner_id, original_filename="cells.pdf", storage_key="documents/cells.pdf",
        mime_type="application/pdf", size_bytes=10, status="ready", page_count=1,
    )
    foreign = Document(
        owner_id=other_id, original_filename="foreign.pdf", storage_key="documents/foreign.pdf",
        mime_type="application/pdf", size_bytes=10, status="ready", page_count=1,
    )
    db.add_all([doc, foreign])
    db.flush()
    vector = [1.0] + [0.0] * 767
    db.add_all([
        DocumentChunk(
            document_id=doc.id, page_start=1, page_end=1, chunk_index=0,
            heading_path=[], text="cells and membranes", text_hash="h1",
            embedding=vector, embedding_model_id="text-embedding-nomic-embed-text-v1.5",
            embedding_dimension=768,
        ),
        DocumentChunk(
            document_id=doc.id, page_start=1, page_end=1, chunk_index=1,
            heading_path=[], text="cells without embedding", text_hash="h2",
            embedding=None,
        ),
        DocumentChunk(
            document_id=foreign.id, page_start=1, page_end=1, chunk_index=0,
            heading_path=[], text="foreign cells", text_hash="h3", embedding=vector,
            embedding_model_id="text-embedding-nomic-embed-text-v1.5",
            embedding_dimension=768,
        ),
    ])
    db.commit()

    async def fake_query_embedding(text):
        return vector

    monkeypatch.setattr(retrieval_module.ai_provider, "get_embedding", fake_query_embedding)
    result = await retrieval_service.hybrid_search(db, "cells", owner_id=owner_id, top_k=5)
    texts = [item["text"] for item in result["results"]]
    assert "cells and membranes" in texts
    assert "cells without embedding" not in texts
    assert "foreign cells" not in texts
```

- [ ] **Step 3: Run the tests and confirm failure**

```powershell
.\.venv\Scripts\python -m pytest tests/test_ai_provider_truth.py tests/test_retrieval_truth.py -q
```

Expected: FAIL — empty text returns zero vectors, wrong dimensions may be accepted by the batch fallback, and retrieval can return null-embedding or foreign chunks.

- [ ] **Step 4: Rewrite the embedding methods**

At the top of `ai_provider.py`:

```python
class EmbeddingUnavailableError(RuntimeError):
    """The configured embedding provider could not produce valid vectors."""
```

Replace `get_embedding` and `get_embeddings_batch` with:

```python
async def get_embedding(self, text: str) -> List[float]:
    vectors = await self.get_embeddings_batch([text])
    return vectors[0]

async def get_embeddings_batch(self, texts: List[str]) -> List[List[float]]:
    if not texts:
        return []
    clean_inputs = [text.strip() for text in texts]
    if any(not text for text in clean_inputs):
        raise ValueError("Cannot embed empty text; remove blank chunks before embedding.")

    url = f"{self.base_url}/embeddings"
    payload = {"model": self.embed_model, "input": clean_inputs}
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(url, json=payload)
    except Exception as exc:
        raise EmbeddingUnavailableError("Embedding provider is unreachable.") from exc

    if response.status_code != 200:
        raise EmbeddingUnavailableError(
            f"Embedding provider returned status {response.status_code}."
        )

    data = response.json()
    items = sorted(data.get("data", []), key=lambda item: item.get("index", 0))
    if len(items) != len(clean_inputs):
        raise ValueError(
            f"Embedding count mismatch: requested {len(clean_inputs)}, received {len(items)}."
        )

    vectors = [item.get("embedding") or [] for item in items]
    for vector in vectors:
        if len(vector) != self.expected_dim:
            raise ValueError(
                f"Embedding dimension mismatch: expected {self.expected_dim}, got {len(vector)}."
            )
    return vectors
```

Delete the `lms` CLI auto-load block and every sequential fallback. `generate_chat` already raises on non-200; leave it.

- [ ] **Step 5: Filter retrieval to valid, owned, ready chunks**

In both SQL statements in `retrieval.py`, add:

```sql
AND d.deleted_at IS NULL
AND d.status IN ('awaiting_review', 'ready')
AND c.embedding IS NOT NULL
AND c.embedding_model_id = :embedding_model
AND c.embedding_dimension = :embedding_dim
```

Add to `params`:

```python
"embedding_model": settings.EMBEDDING_MODEL,
"embedding_dim": settings.EMBEDDING_DIMENSION,
```

Import `settings`. Do not catch `EmbeddingUnavailableError`; let the doubt endpoint translate it into a retryable error in Task 12.

- [ ] **Step 6: Run the tests**

```powershell
.\.venv\Scripts\python -m pytest tests/test_ai_provider_truth.py tests/test_retrieval_truth.py -q
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add backend/app/core/ai_provider.py backend/app/services/retrieval.py backend/tests/test_ai_provider_truth.py backend/tests/test_retrieval_truth.py
git commit -m "fix: reject invalid embeddings and scope retrieval to ready owned chunks"
```

---

### Task 6: Ingestion Quality Gate and All-or-Nothing Indexing

**Files:**
- Modify: `backend/app/services/extraction.py`
- Modify: `backend/app/services/ingestion.py`
- Modify: `backend/app/api/v1/documents.py:169-192`
- Create: `backend/tests/test_ingestion_quality.py`

**Interfaces:**
- Consumes: `storage_service.download_file`, `extraction_service.extract_document`, `chunking_service.create_chunks`, `ai_provider.get_embeddings_batch`.
- Produces: `process_claimed_document` leaves `needs_ocr` when no page has usable text, `failed` with `error_code="embedding_unavailable"` when embeddings fail, and `awaiting_review` only after every chunk has a valid vector. `GET /documents/{id}/status` returns `pagesRead`, `pagesNeedingOcr`, and every page's metadata.

- [ ] **Step 1: Write the failing ingestion tests**

```python
# backend/tests/test_ingestion_quality.py
import uuid
import pytest

from app.core.ai_provider import EmbeddingUnavailableError
from app.models.documents import Document, DocumentChunk, DocumentPage
from app.services import ingestion as ingestion_module
from app.services.ingestion import process_claimed_document


def _document(db):
    doc = Document(
        owner_id=uuid.uuid4(), original_filename="book.pdf",
        storage_key="documents/book.pdf", mime_type="application/pdf",
        size_bytes=100, status="stored", lease_owner="test-worker",
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)
    return doc


def _page(text="Cells are the fundamental unit of life.", needs_ocr=False):
    return {
        "page_number": 1, "text": text, "char_count": len(text),
        "word_count": len(text.split()), "is_scanned_ocr_needed": needs_ocr,
        "extraction_quality": "low" if needs_ocr else "high", "metadata": {},
    }


@pytest.mark.asyncio
async def test_unreadable_document_is_needs_ocr_and_indexes_nothing(db, monkeypatch):
    doc = _document(db)

    async def fake_download(**kwargs):
        return b"not really a pdf"

    monkeypatch.setattr(ingestion_module.storage_service, "download_file", fake_download)
    monkeypatch.setattr(ingestion_module.extraction_service, "extract_document", lambda **kwargs: [_page("", True)])
    await process_claimed_document(db, doc)
    db.refresh(doc)

    assert doc.status == "needs_ocr"
    assert db.query(DocumentChunk).filter(DocumentChunk.document_id == doc.id).count() == 0


@pytest.mark.asyncio
async def test_embedding_failure_leaves_no_partial_chunks(db, monkeypatch):
    doc = _document(db)

    async def fake_download(**kwargs):
        return b"pdf"

    async def failing_embeddings(texts):
        raise EmbeddingUnavailableError("provider down")

    monkeypatch.setattr(ingestion_module.storage_service, "download_file", fake_download)
    monkeypatch.setattr(ingestion_module.extraction_service, "extract_document", lambda **kwargs: [_page()])
    monkeypatch.setattr(ingestion_module.ai_provider, "get_embeddings_batch", failing_embeddings)
    await process_claimed_document(db, doc)
    db.refresh(doc)

    assert doc.status == "failed"
    assert doc.error_code == "embedding_unavailable"
    assert db.query(DocumentChunk).filter(DocumentChunk.document_id == doc.id).count() == 0


@pytest.mark.asyncio
async def test_valid_document_indexes_only_valid_vectors(db, monkeypatch):
    doc = _document(db)

    async def fake_download(**kwargs):
        return b"pdf"

    async def valid_embeddings(texts):
        assert all(text.strip() for text in texts)
        return [[0.25] * 768 for _ in texts]

    monkeypatch.setattr(ingestion_module.storage_service, "download_file", fake_download)
    monkeypatch.setattr(ingestion_module.extraction_service, "extract_document", lambda **kwargs: [_page()])
    monkeypatch.setattr(ingestion_module.ai_provider, "get_embeddings_batch", valid_embeddings)
    await process_claimed_document(db, doc)
    db.refresh(doc)

    chunks = db.query(DocumentChunk).filter(DocumentChunk.document_id == doc.id).all()
    assert doc.status == "awaiting_review"
    assert chunks
    assert all(chunk.embedding is not None for chunk in chunks)
    assert all(chunk.embedding_dimension == 768 for chunk in chunks)


def test_status_reports_all_pages_and_ocr_counts(client, db):
    owner_id = uuid.uuid4()
    doc = Document(
        owner_id=owner_id, original_filename="book.pdf", storage_key="documents/book.pdf",
        mime_type="application/pdf", size_bytes=100, status="awaiting_review", page_count=2,
    )
    db.add(doc)
    db.flush()
    db.add_all([
        DocumentPage(document_id=doc.id, page_number=1, extracted_text="Readable text", char_count=13, word_count=2),
        DocumentPage(document_id=doc.id, page_number=2, extracted_text="", char_count=0, word_count=0, is_scanned_ocr_needed=True, extraction_quality="low"),
    ])
    db.commit()

    response = client.get(f"/api/v1/documents/{doc.id}/status", headers={"X-User-Id": str(owner_id)})
    assert response.status_code == 200
    body = response.json()
    assert body["pagesRead"] == 1
    assert body["pagesNeedingOcr"] == 1
    assert len(body["pages"]) == 2
```

- [ ] **Step 2: Run and confirm failure**

```powershell
.\.venv\Scripts\python -m pytest tests/test_ingestion_quality.py -q
```

Expected: FAIL — unreadable pages contain placeholder text, embeddings may be zero/partial, and status omits page quality counts.

- [ ] **Step 3: Remove placeholder extraction text**

In `backend/app/services/extraction.py`:

- The DOCX unavailable branch must `raise RuntimeError("DOCX extraction is unavailable on this worker.")` instead of returning a page whose text is `"DOCX extractor unavailable"`.
- The PPTX unavailable branch must do the same with `"PPTX extraction is unavailable on this worker."`.
- When a PDF page needs OCR and OCR still fails, set `text=""`, `char_count=0`, `word_count=0`, `extraction_quality="low"`, `is_scanned_ocr_needed=True`. Do not write `[Page N: corrupted font encoding…]`.
- The image OCR fallback must return `text=""`, `char_count=0`, `word_count=0`, `extraction_quality="low"`, `is_scanned_ocr_needed=True`. Do not write `[Uploaded Image File: … scheduled]`.

- [ ] **Step 4: Make ingestion all-or-nothing**

In `process_claimed_document`:

- Keep page rows, but do not add `DocumentChunk` rows until every embedding batch succeeds.
- Replace the per-batch commit with:

```python
embedded_chunks = []
BATCH_SIZE = 16
for batch_start in range(0, len(indexable), BATCH_SIZE):
    batch = indexable[batch_start:batch_start + BATCH_SIZE]
    texts = [(chunk.get("text") or "").strip() for chunk in batch]
    if any(not text for text in texts):
        raise ValueError("Chunk text is empty; refusing to embed blank content.")
    vectors = await ai_provider.get_embeddings_batch(texts)
    if len(vectors) != len(batch):
        raise ValueError("Embedding count does not match the chunk batch.")
    embedded_chunks.extend(zip(batch, vectors))

for chunk, vector in embedded_chunks:
    db.add(DocumentChunk(... embedding=vector ...))
db.commit()
```

- In the `except` block, determine the error code:

```python
if isinstance(exc, EmbeddingUnavailableError) or "embedding" in str(exc).lower():
    failed.error_code = "embedding_unavailable"
    failed.safe_error_message = "The embedding service is unavailable. Retry when it is running."
else:
    failed.error_code = "processing_failed"
    failed.safe_error_message = "The document could not be processed. Retry or upload a readable copy."
```

- Delete any `DocumentChunk` rows for the document in the error handler before committing the failure, so a retry can never leave partial evidence. Keep `DocumentPage` rows for diagnostics.
- Set `doc.status = "awaiting_review"` only after the chunk commit. Set `doc.page_count = len(pages)`.
- If `usable` is empty or every page is `is_scanned_ocr_needed`, keep `needs_ocr` and return before chunking.

- [ ] **Step 5: Expand the status payload truthfully**

In `get_document_status`:

```python
pages_read = sum(1 for page in pages if (page.extracted_text or "").strip())
pages_needing_ocr = sum(1 for page in pages if page.is_scanned_ocr_needed)
payload["pagesRead"] = pages_read
payload["pagesNeedingOcr"] = pages_needing_ocr
payload["pages"] = [
    {
        "pageNumber": page.page_number,
        "charCount": page.char_count,
        "wordCount": page.word_count,
        "quality": page.extraction_quality,
        "needsOcr": page.is_scanned_ocr_needed,
        "preview": (page.extracted_text or "")[:120],
    }
    for page in pages
]
```

Remove the `pages[:10]` slice. The response is page metadata, not full text; 500 pages is acceptable.

- [ ] **Step 6: Run the tests**

```powershell
.\.venv\Scripts\python -m pytest tests/test_ingestion_quality.py -q
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add backend/app/services/extraction.py backend/app/services/ingestion.py backend/app/api/v1/documents.py backend/tests/test_ingestion_quality.py
git commit -m "fix: fail ingestion closed and stop placeholder page text"
```

---

### Task 7: Durable, Validated Lesson Generation

**Files:**
- Create: `backend/alembic/versions/007_lesson_versioning_and_attempt_truth.py`
- Create: `backend/app/services/generation_queue.py`
- Modify: `backend/app/services/lesson_generator.py`
- Modify: `backend/app/worker.py`
- Create: `backend/tests/fixtures.py`
- Create: `backend/tests/test_generation_contracts.py`
- Modify: `backend/tests/test_lesson_validator.py`
- Modify: `backend/tests/test_recovery_contracts.py`

**Interfaces:**
- Consumes: `GenerationJob`, `PathLesson`, `LessonVersion`, `Question`, `lesson_generator_service`.
- Produces: `enqueue_lesson_generation(db, *, owner_id, path, lessons, priority_for=None) -> list[GenerationJob]`; `validate_package` rejects missing source refs, duplicate question IDs, empty answer keys, and empty concept IDs; worker writes `version_number = max + 1` and never publishes a rejected package.

- [ ] **Step 1: Write the test fixture builder**

```python
# backend/tests/fixtures.py
import copy


def valid_lesson_package(lesson_id="lesson-1", path_id="path-1", title="Cell Structure"):
    source_refs = [{
        "citationId": "cite_1", "chunkId": "chunk-1",
        "documentVersionId": "doc-1", "pageStart": 1, "pageEnd": 1,
        "headingPath": ["Chapter 1"], "sourceTitle": "Class 9 Science",
    }]
    return {
        "schemaVersion": "1.0.0", "lessonId": lesson_id, "lessonVersion": 1,
        "pathId": path_id, "pathVersion": 1, "title": title, "grade": 9,
        "subjectId": "subject-science", "languageTag": "en-IN",
        "translationStatus": "original", "estimatedMinutes": 15,
        "sourceRefs": source_refs,
        "objectives": ["Describe the structure.", "Explain the function."],
        "prerequisites": [],
        "blocks": [{
            "blockId": "block-1", "kind": "explanation", "heading": "Introduction",
            "content": "The source explains the structure and function.",
            "sourceRefs": copy.deepcopy(source_refs),
        }],
        "visuals": [{
            "visualId": "vis-1", "type": "concept_map", "altText": "Concept map",
            "spec": {
                "schemaVersion": "1.0.0", "visualId": "vis-1", "type": "concept_map",
                "altText": "Concept map",
                "data": {"nodes": [{"id": "n1", "label": "Cell"}], "edges": []},
            },
        }],
        "workedExamples": [{
            "prompt": "What is the structure?", "steps": ["Read the source."],
            "answer": "The source describes it.", "sourceRefs": copy.deepcopy(source_refs),
        }],
        "practice": [{
            "questionId": "q1", "type": "multiple_choice",
            "prompt": "Which statement matches the source?",
            "options": ["A", "B", "C", "D"], "conceptIds": ["concept-1"],
            "difficulty": "introductory", "answerKey": "A",
            "hints": ["Read the first block."], "feedback": "A matches the source.",
            "sourceRefs": copy.deepcopy(source_refs), "validator": "deterministic",
        }],
        "checkpointTest": [{
            "questionId": "t1", "type": "multiple_choice",
            "prompt": "Which statement is independent evidence?",
            "options": ["A", "B", "C", "D"], "conceptIds": ["concept-1"],
            "difficulty": "standard", "answerKey": "B",
            "hints": [], "feedback": "B is correct.",
            "sourceRefs": copy.deepcopy(source_refs), "validator": "deterministic",
        }],
        "takeaways": ["The source is the authority."],
        "doubtAnchors": [{"anchorId": "block-1", "label": "Ask about this", "sourceRef": source_refs[0]}],
        "validation": {"status": "draft", "checks": []},
    }


def evidence_chunks():
    return [{
        "citationId": "cite_1", "chunkId": "chunk-1", "documentVersionId": "doc-1",
        "pageStart": 1, "pageEnd": 1, "headingPath": ["Chapter 1"],
        "text": "The source explains the structure and function.",
    }]
```

- [ ] **Step 2: Write the failing generation tests**

```python
# backend/tests/test_generation_contracts.py
import copy
import uuid

import pytest

from app.models.jobs import GenerationJob
from app.models.learning import LearningPath, PathLesson, LessonVersion, Question
from app.services.generation_queue import enqueue_lesson_generation
from app.services.lesson_generator import lesson_generator_service
from app.worker import process_job
from tests.fixtures import evidence_chunks, valid_lesson_package


def _path_and_lesson(db):
    owner_id = uuid.uuid4()
    path = LearningPath(
        owner_id=owner_id, grade=9, subject_id="subject-science",
        outline_json={"title": "Cells"}, status="generating",
    )
    db.add(path)
    db.flush()
    lesson = PathLesson(path_id=path.id, lesson_key="lesson_1", title="Cells", sequence=1, status="queued")
    db.add(lesson)
    db.commit()
    return owner_id, path, lesson


def test_validation_rejects_missing_answer_key():
    package = valid_lesson_package()
    package["practice"][0]["answerKey"] = ""
    result = lesson_generator_service.validate_package(package, evidence_chunks())
    assert result["status"] == "rejected"
    assert any(check["name"] == "answer_keys_nonempty" and not check["passed"] for check in result["checks"])


def test_validation_rejects_missing_source_refs():
    package = valid_lesson_package()
    package["sourceRefs"] = []
    result = lesson_generator_service.validate_package(package, evidence_chunks())
    assert result["status"] == "rejected"
    assert any(check["name"] == "source_refs_present" and not check["passed"] for check in result["checks"])


def test_validation_accepts_a_complete_package():
    result = lesson_generator_service.validate_package(valid_lesson_package(), evidence_chunks())
    assert result["status"] == "ready"


def test_enqueue_is_idempotent(db):
    owner_id, path, lesson = _path_and_lesson(db)
    first = enqueue_lesson_generation(db, owner_id=owner_id, path=path, lessons=[lesson])
    second = enqueue_lesson_generation(db, owner_id=owner_id, path=path, lessons=[lesson])
    assert len(first) == 1
    assert len(second) == 1
    assert first[0].id == second[0].id
    assert db.query(GenerationJob).count() == 1


@pytest.mark.asyncio
async def test_provider_failure_does_not_publish_a_lesson(db, monkeypatch):
    owner_id, path, lesson = _path_and_lesson(db)
    job = enqueue_lesson_generation(db, owner_id=owner_id, path=path, lessons=[lesson])[0]

    async def failing_generation(**kwargs):
        raise RuntimeError("chat provider unavailable")

    monkeypatch.setattr(lesson_generator_service, "generate_lesson_package", failing_generation)
    await process_job(db, job)
    db.refresh(job)

    assert job.status in ("retry_wait", "failed")
    assert db.query(LessonVersion).filter(LessonVersion.path_lesson_id == lesson.id).count() == 0


@pytest.mark.asyncio
async def test_rejected_package_creates_no_questions(db, monkeypatch):
    owner_id, path, lesson = _path_and_lesson(db)
    job = enqueue_lesson_generation(db, owner_id=owner_id, path=path, lessons=[lesson])[0]
    package = valid_lesson_package()
    package["practice"][0]["answerKey"] = ""

    async def invalid_generation(**kwargs):
        result = copy.deepcopy(package)
        result["validation"] = lesson_generator_service.validate_package(result, evidence_chunks())
        return result

    monkeypatch.setattr(lesson_generator_service, "generate_lesson_package", invalid_generation)
    await process_job(db, job)
    db.refresh(job)
    db.refresh(lesson)

    versions = db.query(LessonVersion).filter(LessonVersion.path_lesson_id == lesson.id).all()
    assert lesson.status == "failed"
    assert versions and versions[0].validation_status == "rejected"
    assert db.query(Question).count() == 0
```

- [ ] **Step 3: Run and confirm failure**

```powershell
.\.venv\Scripts\python -m pytest tests/test_generation_contracts.py -q
```

Expected: FAIL — `generation_queue` does not exist, validation accepts empty answer keys/source refs, and the worker can save version `1` repeatedly.

- [ ] **Step 4: Write migration `007`**

```python
# backend/alembic/versions/007_lesson_versioning_and_attempt_truth.py
"""lesson versioning, question keys, and attempt truth"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "007"
down_revision: Union[str, None] = "006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Repair databases that already stored duplicate version numbers before the
    # constraint exists. Renumber only lesson groups that actually contain a
    # duplicate, preserving each group's chronological order.
    op.execute(
        """
        WITH ranked AS (
            SELECT id,
                   ROW_NUMBER() OVER (
                       PARTITION BY path_lesson_id
                       ORDER BY version_number, created_at, id
                   ) AS new_version
            FROM lesson_versions
        ),
        dupes AS (
            SELECT path_lesson_id
            FROM lesson_versions
            GROUP BY path_lesson_id
            HAVING COUNT(*) <> COUNT(DISTINCT version_number)
        )
        UPDATE lesson_versions AS lv
        SET version_number = ranked.new_version
        FROM ranked
        JOIN dupes ON dupes.path_lesson_id = ranked.path_lesson_id
        WHERE lv.id = ranked.id
        """
    )
    op.create_unique_constraint(
        "uq_lesson_version_number", "lesson_versions", ["path_lesson_id", "version_number"]
    )
    op.create_unique_constraint(
        "uq_question_key_per_version", "questions", ["lesson_version_id", "question_key"]
    )
    # `001` created a globally unique sync key, which lets one learner's retry
    # block another learner's identical client key. Scope it to the owner.
    inspector = sa.inspect(op.get_bind())
    for constraint in inspector.get_unique_constraints("quiz_attempts"):
        if constraint.get("column_names") == ["sync_idempotency_key"]:
            op.drop_constraint(constraint["name"], "quiz_attempts", type_="unique")
    op.create_unique_constraint(
        "uq_quiz_attempt_owner_sync", "quiz_attempts", ["owner_id", "sync_idempotency_key"]
    )
    op.add_column(
        "quiz_attempts",
        sa.Column("attempt_kind", sa.String(20), nullable=False, server_default="practice"),
    )
    op.add_column(
        "concept_evidence",
        sa.Column("hints_used", sa.Integer(), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    op.drop_column("concept_evidence", "hints_used")
    op.drop_column("quiz_attempts", "attempt_kind")
    op.drop_constraint("uq_quiz_attempt_owner_sync", "quiz_attempts", type_="unique")
    op.create_unique_constraint(
        "quiz_attempts_sync_idempotency_key_key", "quiz_attempts", ["sync_idempotency_key"]
    )
    op.drop_constraint("uq_question_key_per_version", "questions", type_="unique")
    op.drop_constraint("uq_lesson_version_number", "lesson_versions", type_="unique")
```

Update the models: `QuizAttempt.attempt_kind = Column(String(20), default="practice")`; `ConceptEvidence.hints_used = Column(Integer, default=0)`; add `UniqueConstraint("owner_id", "sync_idempotency_key", name="uq_quiz_attempt_owner_sync")` to `QuizAttempt.__table_args__`.

- [ ] **Step 5: Implement the idempotent queue**

```python
# backend/app/services/generation_queue.py
import uuid
from typing import Callable, List

from sqlalchemy.orm import Session

from app.models.jobs import GenerationJob
from app.models.learning import LearningPath, PathLesson


def enqueue_lesson_generation(
    db: Session,
    *,
    owner_id: uuid.UUID,
    path: LearningPath,
    lessons: List[PathLesson],
    priority_for: Callable[[PathLesson], int] | None = None,
) -> List[GenerationJob]:
    jobs: List[GenerationJob] = []
    for lesson in lessons:
        key = f"gen_{path.id}_{lesson.id}_v{path.path_version}"
        existing = db.query(GenerationJob).filter(GenerationJob.idempotency_key == key).first()
        if existing:
            jobs.append(existing)
            continue
        priority = priority_for(lesson) if priority_for else (1 if lesson.sequence <= 2 else 20 + lesson.sequence)
        job = GenerationJob(
            job_type="generate_lesson", owner_id=owner_id, path_id=path.id,
            path_version=path.path_version, lesson_id=lesson.id, priority=priority,
            status="queued", idempotency_key=key,
        )
        db.add(job)
        jobs.append(job)
    db.commit()
    return jobs
```

- [ ] **Step 6: Strengthen validation and delete the fixture**

In `validate_package`, add:

```python
all_questions = package.get("practice", []) + package.get("checkpointTest", [])
source_refs_present = len(package.get("sourceRefs", [])) > 0
answer_keys_present = all(
    str(question.get("answerKey") or "").strip() for question in all_questions
)
concept_ids_present = all(
    len(question.get("conceptIds") or []) > 0 for question in all_questions
)
question_ids = [question.get("questionId") for question in all_questions]
question_ids_unique = all(question_ids) and len(question_ids) == len(set(question_ids))
```

Append checks named `source_refs_present`, `answer_keys_nonempty`, `concept_ids_nonempty`, and `question_ids_unique` to `checks`. Keep the existing schema, citation, visual, and Learn/Solve/Test checks. Delete `_test_fixture_lesson_package` and `_build_deterministic_lesson_package = _test_fixture_lesson_package` entirely.

- [ ] **Step 7: Fix worker versioning and failed states**

In `process_job`:

```python
latest = (
    db.query(func.max(LessonVersion.version_number))
    .filter(LessonVersion.path_lesson_id == lesson.id)
    .scalar()
    or 0
)
version = LessonVersion(
    path_lesson_id=lesson.id, version_number=latest + 1,
    lesson_package_json=package, validation_status=validation_status,
)
```

When `validation_status != "ready"`:

```python
failed_checks = [
    check["name"] for check in package.get("validation", {}).get("checks", [])
    if not check.get("passed")
]
lesson.status = "failed"
job.status = "failed"
job.error_code = "validation_failed"
job.safe_error_message = "Lesson validation failed: " + ", ".join(failed_checks[:3])
```

Do not insert `Question` rows in that branch. On provider exceptions, set `job.error_code = "generation_failed"` and keep the safe message generic (no API keys or raw provider payloads). In the ready branch, store question feedback inside `answer_key_json`:

```python
answer_payload = q_item.get("answerKey")
answer_payload = answer_payload if isinstance(answer_payload, dict) else {"answer": str(answer_payload or "")}
if q_item.get("feedback"):
    answer_payload["feedback"] = q_item["feedback"]
if q_item.get("validator"):
    answer_payload["validator"] = q_item["validator"]
```

- [ ] **Step 8: Update the regression contracts**

In `test_lesson_validator.py`, import `valid_lesson_package` and `evidence_chunks` from `tests.fixtures` instead of any production fixture. In `test_recovery_contracts.py`, replace the string-absence assertion with:

```python
def test_production_generator_has_no_test_fixture():
    source = Path(__file__).resolve().parents[1] / "app" / "services" / "lesson_generator.py"
    text = source.read_text(encoding="utf-8")
    assert "_test_fixture" not in text
    assert "_build_deterministic" not in text
```

- [ ] **Step 9: Run the tests**

```powershell
.\.venv\Scripts\python -m pytest tests/test_generation_contracts.py tests/test_lesson_validator.py tests/test_recovery_contracts.py -q
```

Expected: PASS. A provider failure leaves no version; a rejected package leaves a rejected version and zero questions; enqueue twice returns the same job.

- [ ] **Step 10: Commit**

```bash
git add backend/alembic/versions/007_lesson_versioning_and_attempt_truth.py backend/app/services/generation_queue.py backend/app/services/lesson_generator.py backend/app/worker.py backend/app/models/learning.py backend/tests/fixtures.py backend/tests/test_generation_contracts.py backend/tests/test_lesson_validator.py backend/tests/test_recovery_contracts.py
git commit -m "feat: validate and durably version generated lessons"
```

---

### Task 8: Require Real Context Before Building a Learning Path

**Files:**
- Modify: `backend/app/api/v1/learning_paths.py:15-158`
- Modify: `backend/tests/test_recovery_contracts.py` (`CreatePathRequest` validation)
- Modify: `frontend/src/services/api.ts:310-315`
- Modify: `frontend/src/pages/HomePage.tsx:35-37,223-244,574-594`
- Create: `backend/tests/test_learning_path_creation.py`

**Interfaces:**
- Consumes: `Document`, `DocumentChunk`, `Subject`, `enqueue_lesson_generation`.
- Produces: `POST /learning-paths` requires `documentId`, `grade` (6–10), and `subjectId` (a real active `subjects.id`); it returns `409` if the document has no valid indexed chunks or an active path already exists; it queues exactly one job per created lesson.

- [ ] **Step 1: Write the failing path tests**

```python
# backend/tests/test_learning_path_creation.py
import uuid

from app.models.documents import Document, DocumentChunk, DocumentPage
from app.models.jobs import GenerationJob
from app.models.learning import LearningPath, PathLesson


def _ready_document(db, owner_id):
    doc = Document(
        owner_id=owner_id, original_filename="Class_9_Science.pdf",
        storage_key=f"documents/{owner_id}/book.pdf", mime_type="application/pdf",
        size_bytes=100, status="awaiting_review", page_count=2,
    )
    db.add(doc)
    db.flush()
    db.add_all([
        DocumentPage(document_id=doc.id, page_number=1, extracted_text="Chapter 1: The Cell\nCells are the unit of life.", char_count=50, word_count=10),
        DocumentPage(document_id=doc.id, page_number=2, extracted_text="Chapter 2: Tissues\nTissues are groups of cells.", char_count=50, word_count=10),
    ])
    db.add(DocumentChunk(
        document_id=doc.id, page_start=1, page_end=2, chunk_index=0,
        heading_path=["Chapter 1"], text="Cells are the unit of life. Tissues are groups of cells.",
        text_hash="hash", embedding=[0.1] * 768,
        embedding_model_id="text-embedding-nomic-embed-text-v1.5", embedding_dimension=768,
    ))
    db.commit()
    return doc


def test_path_requires_explicit_grade_and_subject(client, db):
    owner_id = uuid.uuid4()
    doc = _ready_document(db, owner_id)
    response = client.post(
        "/api/v1/learning-paths",
        headers={"X-User-Id": str(owner_id)},
        json={"documentId": str(doc.id)},
    )
    assert response.status_code == 422


def test_path_requires_a_real_subject(client, db):
    owner_id = uuid.uuid4()
    doc = _ready_document(db, owner_id)
    response = client.post(
        "/api/v1/learning-paths",
        headers={"X-User-Id": str(owner_id)},
        json={"documentId": str(doc.id), "grade": 9, "subjectId": "subject-not-real"},
    )
    assert response.status_code == 422


def test_path_queues_one_job_per_lesson(client, db):
    owner_id = uuid.uuid4()
    doc = _ready_document(db, owner_id)
    response = client.post(
        "/api/v1/learning-paths",
        headers={"X-User-Id": str(owner_id)},
        json={"documentId": str(doc.id), "grade": 9, "subjectId": "subject-science"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["totalLessons"] >= 1
    lessons = db.query(PathLesson).filter(PathLesson.path_id == uuid.UUID(body["pathId"])).all()
    jobs = db.query(GenerationJob).filter(GenerationJob.path_id == uuid.UUID(body["pathId"])).all()
    assert len(lessons) == body["totalLessons"]
    assert len(jobs) == len(lessons)


def test_duplicate_path_is_rejected(client, db):
    owner_id = uuid.uuid4()
    doc = _ready_document(db, owner_id)
    payload = {"documentId": str(doc.id), "grade": 9, "subjectId": "subject-science"}
    headers = {"X-User-Id": str(owner_id)}
    assert client.post("/api/v1/learning-paths", headers=headers, json=payload).status_code == 200
    assert client.post("/api/v1/learning-paths", headers=headers, json=payload).status_code == 409


def test_document_without_indexed_chunks_is_rejected(client, db):
    owner_id = uuid.uuid4()
    doc = _ready_document(db, owner_id)
    db.query(DocumentChunk).filter(DocumentChunk.document_id == doc.id).delete()
    db.commit()
    response = client.post(
        "/api/v1/learning-paths",
        headers={"X-User-Id": str(owner_id)},
        json={"documentId": str(doc.id), "grade": 9, "subjectId": "subject-science"},
    )
    assert response.status_code == 409
```

- [ ] **Step 2: Run and confirm failure**

```powershell
.\.venv\Scripts\python -m pytest tests/test_learning_path_creation.py -q
```

Expected: FAIL — the API accepts missing grade/subject, falls back to `0`/`subject-general`, and duplicates paths.

- [ ] **Step 3: Make the request contract explicit**

Replace `OutlineRequest` and `CreatePathRequest` with:

```python
class OutlineRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    document_id: uuid.UUID = Field(alias="documentId")
    grade: int = Field(ge=6, le=10)
    subject_id: str = Field(alias="subjectId", min_length=3)
    language_tag: Optional[str] = None


class CreatePathRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    document_id: uuid.UUID = Field(alias="documentId")
    grade: int = Field(ge=6, le=10)
    subject_id: str = Field(alias="subjectId", min_length=3)
    title: Optional[str] = None
    language_tag: Optional[str] = None
    goal: str = "concept_understanding"
```

Remove `documentVersionId`, `subject`, and every default `9`/`subject-science`.

Update the existing contract test in `backend/tests/test_recovery_contracts.py` so it supplies the newly required field:

```python
def test_create_path_accepts_document_id_alias():
    document_id = uuid.uuid4()
    req = CreatePathRequest.model_validate(
        {"documentId": str(document_id), "grade": 8, "subjectId": "subject-math"}
    )
    assert req.document_id == document_id
    assert req.subject_id == "subject-math"
```

- [ ] **Step 4: Validate the subject and indexed content**

At the start of both handlers:

```python
subject = db.query(Subject).filter(
    Subject.id == req.subject_id, Subject.active == True
).first()
if not subject:
    raise HTTPException(status_code=422, detail="Choose a subject from the curriculum catalogue.")
```

For `create_learning_path`, also:

```python
indexed_chunks = db.query(DocumentChunk).filter(
    DocumentChunk.document_id == doc.id,
    DocumentChunk.embedding.isnot(None),
    DocumentChunk.embedding_dimension == settings.EMBEDDING_DIMENSION,
).count()
if indexed_chunks == 0:
    raise HTTPException(
        status_code=409,
        detail="This document has no indexed text yet. Wait for processing to finish or retry it.",
    )

existing = db.query(LearningPath).filter(
    LearningPath.owner_id == owner_id,
    LearningPath.document_id == doc.id,
    LearningPath.grade == req.grade,
    LearningPath.subject_id == req.subject_id,
    LearningPath.status.in_(["active", "generating"]),
).first()
if existing:
    raise HTTPException(
        status_code=409,
        detail={"code": "path_exists", "pathId": str(existing.id), "message": "A learning path already exists for this document and class."},
    )
```

Import `Subject`, `DocumentChunk`, `settings`.

- [ ] **Step 5: Use the idempotent queue**

Replace the manual `GenerationJob` creation with:

```python
from app.services.generation_queue import enqueue_lesson_generation

jobs = enqueue_lesson_generation(db, owner_id=owner_id, path=path, lessons=created_lessons)
```

Create `created_lessons` while iterating chapters. Keep the first lesson and response shape. Do not create jobs before the path/lessons are flushed.

- [ ] **Step 6: Send real context from Home**

In `HomePage.tsx`, add state initialized from the signed-in profile:

```tsx
const [pathGrade, setPathGrade] = useState<string>(user?.grade ? String(user.grade) : '');
const [pathSubject, setPathSubject] = useState<string>(user?.subjectsInterested?.[0] || '');
```

In the review modal, render a class select (6–10) and a subject select populated from `user.subjectsInterested`. If either is empty, show "Finish onboarding to set your class and subject." and disable the build button. In `handleCreatePathFromOutline`, send:

```tsx
await api.createLearningPath({
  documentId: reviewOutline.documentId,
  grade: Number(pathGrade),
  subjectId: pathSubject,
});
```

Update `api.createLearningPath` to accept `{ documentId: string; grade: number; subjectId: string }`.

- [ ] **Step 7: Run the tests**

```powershell
.\.venv\Scripts\python -m pytest tests/test_learning_path_creation.py tests/test_recovery_contracts.py -q
```

Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add backend/app/api/v1/learning_paths.py backend/tests/test_recovery_contracts.py frontend/src/services/api.ts frontend/src/pages/HomePage.tsx backend/tests/test_learning_path_creation.py
git commit -m "feat: require real class and subject before path creation"
```

---

### Task 9: Server-Grade Every Attempt and Record Real Evidence

**Files:**
- Create: `backend/app/services/attempt_service.py`
- Modify: `backend/app/api/v1/attempts.py`
- Modify: `backend/app/models/learning.py`
- Modify: `backend/app/services/adaptive_engine.py` (use per-evidence hints)
- Create: `backend/tests/test_attempt_grading.py`

**Interfaces:**
- Consumes: `Question`, `LessonVersion`, `PathLesson`, `LearningPath`, `QuizAttempt`, `ConceptEvidence`, `ConceptMasterySnapshot`, `adaptive_engine`, `enqueue_lesson_generation`.
- Produces: `grade_response(question, response) -> tuple[bool, float, str]`; `grade_and_record_attempt(db, *, owner_id, lesson_version_id, question_key, response, hint_level=0, hints_used=None, elapsed_seconds=0, attempt_kind="practice", idempotency_key=None) -> AttemptOutcome`; `POST /attempts` accepts no client correctness and returns `attemptId`, `isCorrect`, `score`, `feedback`, `mastery`, `nextAction`, `alreadyRecorded`.

- [ ] **Step 1: Write the failing attempt tests**

```python
# backend/tests/test_attempt_grading.py
import uuid

from app.models.learning import (
    ConceptEvidence, ConceptMasterySnapshot, LearningPath, LessonVersion,
    PathLesson, Question, QuizAttempt, StudyEvent,
)


def _seed_question(db, owner_id, *, question_type="multiple_choice", answer="A", concept_ids=None):
    path = LearningPath(owner_id=owner_id, grade=9, subject_id="subject-science", outline_json={"title": "Cells"})
    db.add(path)
    db.flush()
    lesson = PathLesson(path_id=path.id, lesson_key="lesson_1", title="Cells", sequence=1, status="ready")
    db.add(lesson)
    db.flush()
    version = LessonVersion(path_lesson_id=lesson.id, version_number=1, lesson_package_json={"title": "Cells"}, validation_status="ready")
    db.add(version)
    db.flush()
    question = Question(
        lesson_version_id=version.id, question_key="q1", type=question_type,
        prompt_json={"text": "Choose A"}, answer_key_json={"answer": answer, "feedback": "A is correct."},
        concept_ids=concept_ids or ["concept-1"], difficulty="standard", validation_status="ready",
    )
    db.add(question)
    db.commit()
    return version, question


def _payload(version, key="attempt-1", response="A", **overrides):
    body = {
        "lessonVersionId": str(version.id), "questionKey": "q1", "response": response,
        "hintLevel": 0, "hintsUsed": [], "elapsedSeconds": 42,
        "attemptKind": "practice", "syncIdempotencyKey": key,
    }
    body.update(overrides)
    return body


def test_wrong_answer_cannot_be_forced_correct(client, db):
    owner_id = uuid.uuid4()
    version, _ = _seed_question(db, owner_id, answer="A")
    response = client.post(
        "/api/v1/attempts", headers={"X-User-Id": str(owner_id)},
        json=_payload(version, response="B", **{"isCorrect": True, "score": 1.0}),
    )
    assert response.status_code == 200
    assert response.json()["isCorrect"] is False
    assert response.json()["score"] == 0.0


def test_correct_answer_records_evidence_and_exact_time(client, db):
    owner_id = uuid.uuid4()
    version, _ = _seed_question(db, owner_id, answer="A", concept_ids=["concept-1", "concept-2"])
    response = client.post(
        "/api/v1/attempts", headers={"X-User-Id": str(owner_id)}, json=_payload(version)
    )
    assert response.status_code == 200
    attempt = db.query(QuizAttempt).filter(QuizAttempt.owner_id == owner_id).one()
    assert attempt.is_correct is True
    assert attempt.elapsed_seconds == 42
    assert db.query(ConceptEvidence).filter(ConceptEvidence.source_attempt_id == attempt.id).count() == 2
    event = db.query(StudyEvent).filter(StudyEvent.owner_id == owner_id).one()
    assert event.seconds == 42
    assert db.query(ConceptMasterySnapshot).filter(ConceptMasterySnapshot.owner_id == owner_id).count() == 2


def test_duplicate_idempotency_key_is_applied_once(client, db):
    owner_id = uuid.uuid4()
    version, _ = _seed_question(db, owner_id)
    headers = {"X-User-Id": str(owner_id)}
    first = client.post("/api/v1/attempts", headers=headers, json=_payload(version))
    second = client.post("/api/v1/attempts", headers=headers, json=_payload(version))
    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json()["alreadyRecorded"] is True
    assert db.query(QuizAttempt).filter(QuizAttempt.owner_id == owner_id).count() == 1
    assert db.query(ConceptEvidence).filter(ConceptEvidence.owner_id == owner_id).count() == 1


def test_other_users_question_is_not_found(client, db):
    owner_id = uuid.uuid4()
    other_id = uuid.uuid4()
    version, _ = _seed_question(db, owner_id)
    response = client.post(
        "/api/v1/attempts", headers={"X-User-Id": str(other_id)}, json=_payload(version)
    )
    assert response.status_code == 404
    assert db.query(QuizAttempt).count() == 0


def test_unsupported_question_type_is_rejected(client, db):
    owner_id = uuid.uuid4()
    version, _ = _seed_question(db, owner_id, question_type="essay")
    response = client.post(
        "/api/v1/attempts", headers={"X-User-Id": str(owner_id)}, json=_payload(version)
    )
    assert response.status_code == 422
    assert db.query(QuizAttempt).count() == 0


def test_three_correct_checkpoint_attempts_reach_demonstrated(client, db):
    owner_id = uuid.uuid4()
    version, _ = _seed_question(db, owner_id)
    headers = {"X-User-Id": str(owner_id)}
    third = None
    for index in range(3):
        third = client.post(
            "/api/v1/attempts", headers=headers,
            json=_payload(version, key=f"attempt-{index}", attemptKind="checkpoint"),
        )
        assert third.status_code == 200
    assert third.json()["mastery"]["band"] == "demonstrated"
```

- [ ] **Step 2: Run and confirm failure**

```powershell
.\.venv\Scripts\python -m pytest tests/test_attempt_grading.py -q
```

Expected: FAIL — the API requires a client-supplied `is_correct`, does not accept `questionKey`, and `max(elapsed_seconds, 30)` invents time.

- [ ] **Step 3: Implement `attempt_service.py`**

```python
class AttemptNotFoundError(Exception): ...
class UnsupportedQuestionTypeError(Exception): ...
class InvalidAnswerKeyError(Exception): ...


@dataclass(frozen=True)
class AttemptOutcome:
    attempt_id: uuid.UUID
    is_correct: bool
    score: float
    feedback: str
    mastery: dict
    next_action: dict
    already_recorded: bool


def _normalize(value: Any) -> str:
    return " ".join(str(value).split()).strip().casefold()


def grade_response(question: Question, response: Any) -> tuple[bool, float, str]:
    answer_key = question.answer_key_json or {}
    expected = answer_key.get("answer")
    if expected is None or str(expected).strip() == "":
        raise InvalidAnswerKeyError("This question has no validated answer key.")
    feedback = str(answer_key.get("feedback") or "")

    if question.type == "multiple_choice":
        correct = _normalize(response) == _normalize(expected)
    elif question.type == "numeric":
        try:
            given_value = float(str(response).strip())
            expected_value = float(str(expected).strip())
        except (TypeError, ValueError) as exc:
            raise ValueError("Enter a numeric answer.") from exc
        correct = abs(given_value - expected_value) <= max(1e-6, abs(expected_value) * 0.001)
    elif question.type == "short_text":
        accepted = answer_key.get("acceptedAnswers") or [expected]
        correct = _normalize(response) in {_normalize(item) for item in accepted}
    else:
        raise UnsupportedQuestionTypeError(
            f"Question type '{question.type}' cannot be graded deterministically."
        )
    return correct, 1.0 if correct else 0.0, feedback
```

`grade_and_record_attempt` must:

1. Resolve `Question` by `(lesson_version_id, question_key)`. If missing, raise `AttemptNotFoundError`.
2. Resolve `LessonVersion -> PathLesson -> LearningPath` and check `LearningPath.owner_id == owner_id`; otherwise raise `AttemptNotFoundError`.
3. Return the existing attempt if `idempotency_key` matches the owner, with `already_recorded=True`.
4. Call `grade_response`.
5. Insert `QuizAttempt` with `attempt_kind`.
6. Insert one `ConceptEvidence` per `question.concept_ids`, copying `hints_used` and `reason` (do not use the current request's hint count for every historical row).
7. Recompute mastery per concept from all evidence using each row's own `hints_used`.
8. Upsert `ConceptMasterySnapshot`.
9. Insert a `StudyEvent` with `event_type=attempt_kind`, `seconds=elapsed_seconds`, `score=score`.
10. If the mastery band is `developing` and `attempt_kind == "checkpoint"` and no remediation lesson exists, insert one `PathLesson` with key `rem_{lesson.sequence}_{concept_id[:16]}` and call `enqueue_lesson_generation` for it.
11. Commit once and return the first concept's mastery plus `adaptive_engine.determine_next_action(mastery)`.

- [ ] **Step 4: Replace the API contract**

```python
class AttemptRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    lesson_version_id: uuid.UUID = Field(alias="lessonVersionId")
    question_key: str = Field(alias="questionKey")
    response: Any
    hint_level: int = Field(default=0, ge=0, le=10, alias="hintLevel")
    hints_used: Optional[List[str]] = Field(default=None, alias="hintsUsed")
    elapsed_seconds: int = Field(default=0, ge=0, le=1800, alias="elapsedSeconds")
    attempt_kind: Literal["practice", "checkpoint"] = Field(default="practice", alias="attemptKind")
    sync_idempotency_key: Optional[str] = Field(default=None, alias="syncIdempotencyKey")
```

Keep `populate_by_name=True` so existing snake_case callers and tests still validate. Accept both spellings; the frontend and sync manager send camelCase, and `isCorrect`/`score` are deliberately not part of the model so a client cannot influence grading.

The endpoint calls `grade_and_record_attempt` and maps errors:

```python
except AttemptNotFoundError:
    raise HTTPException(status_code=404, detail="Question not found for this lesson.")
except (UnsupportedQuestionTypeError, InvalidAnswerKeyError, ValueError) as exc:
    raise HTTPException(status_code=422, detail=str(exc))
```

Return camelCase fields. Delete the inline grading/evidence/remediation block from `attempts.py`; the service owns it.

- [ ] **Step 5: Use per-evidence hints in mastery**

In `adaptive_engine.calculate_mastery`, keep the existing algorithm but ensure the caller passes `hints_used` from each `ConceptEvidence` row. In `attempt_service`, build:

```python
e_records = [
    {"outcome": evidence.outcome, "hints_used": evidence.hints_used or 0}
    for evidence in all_evidence
]
```

Do not reuse `req.hint_level` for historical rows.

- [ ] **Step 6: Run the tests**

```powershell
.\.venv\Scripts\python -m pytest tests/test_attempt_grading.py -q
```

Expected: PASS. A wrong response stays wrong even if the client sends `isCorrect: true`; duplicate keys create one attempt; three correct checkpoint attempts reach `demonstrated`; unsupported types return `422`.

- [ ] **Step 7: Commit**

```bash
git add backend/app/services/attempt_service.py backend/app/api/v1/attempts.py backend/app/models/learning.py backend/app/services/adaptive_engine.py backend/tests/test_attempt_grading.py
git commit -m "feat: grade attempts on the server and record real evidence"
```

### Task 10: Make Learn → Solve → Test Record Server-Graded Evidence

**Files:**
- Modify: `backend/app/api/v1/learning_paths.py` (`get_lesson`)
- Modify: `backend/app/api/v1/attempts.py`
- Modify: `backend/app/services/attempt_service.py`
- Modify: `frontend/src/services/api.ts`
- Modify: `frontend/src/pages/LessonReaderPage.tsx`
- Modify: `frontend/src/db/indexedDB.ts` (attempt shape only; user scoping is Task 11)
- Create: `backend/tests/test_lesson_package_redaction.py`
- Create: `frontend/e2e/lesson_attempts.spec.ts`

**Interfaces:**
- Consumes: `GET /learning-paths/lessons/{lesson_id}` returns `lessonVersionId`; `POST /attempts` from Task 9.
- Produces: lesson packages served to students never contain `answerKey`; `AttemptOutcome.correct_answer` and the API field `correctAnswer` are populated only after server grading; `api.submitAttempt(input: AttemptSubmission): Promise<AttemptResult>`; practice/checkpoint answers are never scored in the browser and no request contains `isCorrect` or `score`; reading events use measured seconds.

- [ ] **Step 1: Write the failing package-redaction tests**

```python
# backend/tests/test_lesson_package_redaction.py
import uuid

from app.models.learning import LearningPath, LessonVersion, PathLesson, Question


def _ready_lesson(db, owner_id):
    path = LearningPath(
        owner_id=owner_id, grade=9, subject_id="subject-science",
        outline_json={"title": "Cells"}, status="active",
    )
    db.add(path)
    db.flush()
    lesson = PathLesson(path_id=path.id, lesson_key="lesson_1", title="Cells", sequence=1, status="ready")
    db.add(lesson)
    db.flush()
    version = LessonVersion(
        path_lesson_id=lesson.id, version_number=1, validation_status="ready",
        lesson_package_json={
            "title": "Cells", "grade": 9, "subjectId": "subject-science",
            "practice": [{
                "questionId": "q1", "type": "multiple_choice", "prompt": "Choose one",
                "options": ["Cell", "Tissue"], "conceptIds": ["concept-cell"],
                "answerKey": "Cell", "feedback": "The cell is the unit.",
            }],
            "checkpointTest": [{
                "questionId": "t1", "type": "multiple_choice", "prompt": "Choose one",
                "options": ["A", "B"], "conceptIds": ["concept-cell"],
                "answerKey": "B", "feedback": "B is correct.",
            }],
        },
    )
    db.add(version)
    db.flush()
    db.add(Question(
        lesson_version_id=version.id, question_key="q1", type="multiple_choice",
        prompt_json={"text": "Choose one"}, answer_key_json={"answer": "Cell", "feedback": "The cell is the unit."},
        concept_ids=["concept-cell"], validation_status="ready",
    ))
    db.commit()
    return lesson, version


def test_lesson_package_never_exposes_answer_keys(client, db):
    owner_id = uuid.uuid4()
    lesson, version = _ready_lesson(db, owner_id)
    response = client.get(
        f"/api/v1/learning-paths/lessons/{lesson.id}",
        headers={"X-User-Id": str(owner_id)},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["lessonVersionId"] == str(version.id)
    assert "answerKey" not in body["practice"][0]
    assert "answerKey" not in body["checkpointTest"][0]


def test_correct_answer_is_returned_only_after_grading(client, db):
    owner_id = uuid.uuid4()
    _, version = _ready_lesson(db, owner_id)
    response = client.post(
        "/api/v1/attempts",
        headers={"X-User-Id": str(owner_id)},
        json={
            "lessonVersionId": str(version.id), "questionKey": "q1", "response": "Tissue",
            "hintLevel": 0, "hintsUsed": [], "elapsedSeconds": 12,
            "attemptKind": "practice", "syncIdempotencyKey": "redaction-attempt-1",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["isCorrect"] is False
    assert body["correctAnswer"] == "Cell"
```

- [ ] **Step 2: Write the failing lesson-runner E2E test**

```ts
// frontend/e2e/lesson_attempts.spec.ts
import { test, expect } from '@playwright/test';

const profile = {
  id: '33333333-3333-4333-8333-333333333333',
  email: 'student@example.com',
  role: 'student',
  displayName: 'Test Student',
  grade: 9,
  boardId: 'board-cbse',
  onboardingCompleted: true,
  tourCompleted: true,
};

const lessonPackage = {
  lessonId: 'lesson-1',
  lessonVersionId: '11111111-1111-4111-8111-111111111111',
  pathId: '22222222-2222-4222-8222-222222222222',
  title: 'Cell Structure',
  grade: 9,
  subjectId: 'subject-science',
  objectives: [],
  blocks: [],
  visuals: [],
  workedExamples: [],
  takeaways: [],
  practice: [{
    questionId: 'q1',
    type: 'multiple_choice',
    prompt: 'Which is the basic unit of life?',
    options: ['Cell', 'Tissue', 'Organ', 'Organism'],
    conceptIds: ['concept-cell'],
    hints: ['Read the first block.'],
    feedback: 'The cell is the basic unit.',
  }],
  checkpointTest: [{
    questionId: 't1',
    type: 'multiple_choice',
    prompt: 'Which statement is independent evidence?',
    options: ['A', 'B', 'C', 'D'],
    conceptIds: ['concept-cell'],
    hints: [],
    feedback: 'B is correct.',
  }],
};

async function signIn(page: import('@playwright/test').Page) {
  await page.addInitScript(() => {
    localStorage.setItem('setu_auth_token', 'e2e-token');
    localStorage.setItem('setu_active_user_id', '33333333-3333-4333-8333-333333333333');
  });
  await page.route(/\/api\/v1\/profile$/, (route) => route.fulfill({ json: profile }));
  await page.route('**/api/v1/learning-paths/lessons/**', (route) => route.fulfill({ json: lessonPackage }));
}

test('practice is graded by the server and never trusts client correctness', async ({ page }) => {
  await signIn(page);
  let body: any = null;
  await page.route('**/api/v1/attempts', async (route) => {
    body = route.request().postDataJSON();
    await route.fulfill({
      json: {
        attemptId: 'att-1', isCorrect: false, score: 0,
        correctAnswer: 'Cell', feedback: 'Not quite. Re-read the first block.',
        mastery: { band: 'developing', score: 0, evidenceCount: 1, explanation: 'One incorrect response.' },
        nextAction: { action: 'review_prerequisite', title: 'Review Prerequisite Concepts', reason: 'Review the source.', canAdvance: true },
        alreadyRecorded: false,
      },
    });
  });

  await page.goto('/lesson/lesson-1?pathId=22222222-2222-4222-8222-222222222222');
  await page.getByRole('button', { name: /2\. Solve/ }).click();
  await page.getByRole('button', { name: 'B. Tissue' }).click();
  await page.getByRole('button', { name: 'Check Answer' }).click();

  await expect(page.getByText('Not quite. Re-read the first block.')).toBeVisible();
  expect(body.isCorrect).toBeUndefined();
  expect(body.score).toBeUndefined();
  expect(body.questionKey).toBe('q1');
  expect(body.lessonVersionId).toBe(lessonPackage.lessonVersionId);
  expect(body.attemptKind).toBe('practice');
});

test('checkpoint shows server mastery and no teacher-only link', async ({ page }) => {
  await signIn(page);
  const bodies: any[] = [];
  await page.route('**/api/v1/attempts', async (route) => {
    bodies.push(route.request().postDataJSON());
    await route.fulfill({
      json: {
        attemptId: `att-${bodies.length}`, isCorrect: true, score: 1,
        correctAnswer: 'B', feedback: 'B is correct.',
        mastery: { band: 'demonstrated', score: 1, evidenceCount: 3, explanation: 'Three independent correct observations.' },
        nextAction: { action: 'move_forward', title: 'Advance to Next Lesson', reason: 'Mastery demonstrated.', canAdvance: true },
        alreadyRecorded: false,
      },
    });
  });

  await page.goto('/lesson/lesson-1?pathId=22222222-2222-4222-8222-222222222222');
  await page.getByRole('button', { name: /3\. Test/ }).click();
  await page.getByRole('button', { name: 'B. B' }).click();
  await page.getByRole('button', { name: 'Submit Checkpoint Test' }).click();

  await expect(page.getByText(/demonstrated/i)).toBeVisible();
  await expect(page.getByRole('button', { name: /Teacher Evidence Matrix/ })).toHaveCount(0);
  expect(bodies).toHaveLength(1);
  expect(bodies[0].attemptKind).toBe('checkpoint');
  expect(bodies[0].isCorrect).toBeUndefined();
});
```

- [ ] **Step 3: Run both tests and confirm failure**

```powershell
cd backend
.\.venv\Scripts\python -m pytest tests/test_lesson_package_redaction.py -q
cd ..\frontend
npm run build
npx playwright test e2e/lesson_attempts.spec.ts --project=chromium
```

Expected: FAIL — the lesson response exposes `answerKey`, `correctAnswer` is absent, and the page compares answers locally instead of calling `/attempts`.

- [ ] **Step 4: Redact answer keys and extend the graded result**

In `learning_paths.py`, add:

```python
import copy


def _redact_answer_keys(package: dict) -> dict:
    sanitized = copy.deepcopy(package)
    for section in ("practice", "checkpointTest"):
        for question in sanitized.get(section, []) or []:
            question.pop("answerKey", None)
    return sanitized
```

In `get_lesson`, replace the Task 4 package block with:

```python
package = _redact_answer_keys(dict(version.lesson_package_json))
package["lessonVersionId"] = str(version.id)
return package
```

In `attempt_service.py`, change `grade_response` to return the expected answer:

```python
def grade_response(question: Question, response: Any) -> tuple[bool, float, str, Any]:
    answer_key = question.answer_key_json or {}
    expected = answer_key.get("answer")
    ...
    return correct, 1.0 if correct else 0.0, feedback, expected
```

Add `correct_answer: Any` to `AttemptOutcome` and populate it in `grade_and_record_attempt`. In `attempts.py`, add `"correctAnswer": outcome.correct_answer` to the response.

- [ ] **Step 5: Add typed attempt submission to the API client**

```ts
export interface AttemptSubmission {
  lessonVersionId: string;
  questionKey: string;
  response: unknown;
  hintLevel?: number;
  hintsUsed?: string[];
  elapsedSeconds?: number;
  attemptKind?: 'practice' | 'checkpoint';
  syncIdempotencyKey?: string;
}

export interface AttemptResult {
  attemptId: string;
  isCorrect: boolean;
  score: number;
  correctAnswer?: unknown;
  feedback: string;
  mastery: { band: string; score: number; evidenceCount: number; explanation: string };
  nextAction: {
    action: string;
    title: string;
    reason: string;
    canAdvance: boolean;
    remediationInjected?: boolean;
    remediationLessonId?: string;
  };
  alreadyRecorded: boolean;
}

async submitAttempt(data: AttemptSubmission): Promise<AttemptResult> {
  return request<AttemptResult>('/attempts', {
    method: 'POST',
    body: JSON.stringify(data),
  });
}
```

- [ ] **Step 6: Rewrite practice submission in `LessonReaderPage.tsx`**

Add state:

```tsx
const [attemptResults, setAttemptResults] = useState<Record<string, AttemptResult>>({});
const [attemptErrors, setAttemptErrors] = useState<Record<string, string>>({});
const [submittingQuestion, setSubmittingQuestion] = useState<string | null>(null);
```

Track when each question first becomes active:

```tsx
const questionStartedAt = useRef<Record<string, number>>({});
const markQuestionStarted = (questionId: string) => {
  if (!questionStartedAt.current[questionId]) {
    questionStartedAt.current[questionId] = Date.now();
  }
};
```

Call `markQuestionStarted(q.questionId)` from `handlePracticeSelect` and `handleRevealHint`. Replace `handlePracticeSubmit` with:

```tsx
const handlePracticeSubmit = async (q: any) => {
  const selected = practiceAnswers[q.questionId];
  if (!selected || !lessonPackage?.lessonVersionId) return;

  const startedAt = questionStartedAt.current[q.questionId] || Date.now();
  const elapsedSeconds = Math.max(0, Math.min(1800, Math.round((Date.now() - startedAt) / 1000)));
  const hintsUsed = (q.hints || []).slice(0, revealedHints[q.questionId] || 0);
  const payload: AttemptSubmission = {
    lessonVersionId: lessonPackage.lessonVersionId,
    questionKey: q.questionId,
    response: selected,
    hintLevel: hintsUsed.length,
    hintsUsed,
    elapsedSeconds,
    attemptKind: 'practice',
    syncIdempotencyKey: `practice-${lessonPackage.lessonVersionId}-${q.questionId}`,
  };

  setSubmittingQuestion(q.questionId);
  setAttemptErrors((prev) => ({ ...prev, [q.questionId]: '' }));
  try {
    const result = await api.submitAttempt(payload);
    setAttemptResults((prev) => ({ ...prev, [q.questionId]: result }));
  } catch (err: any) {
    if (!navigator.onLine) {
      await queueAttemptOffline({
        clientAttemptId: payload.syncIdempotencyKey!,
        lessonId,
        lessonVersionId: payload.lessonVersionId,
        questionKey: payload.questionKey,
        response: payload.response,
        hintLevel: payload.hintLevel || 0,
        hintsUsed: payload.hintsUsed || [],
        attemptKind: payload.attemptKind || 'practice',
        elapsedSeconds: payload.elapsedSeconds || 0,
      });
      setAttemptErrors((prev) => ({
        ...prev,
        [q.questionId]: 'Saved offline. This answer will be graded when you reconnect.',
      }));
    } else {
      setAttemptErrors((prev) => ({
        ...prev,
        [q.questionId]: err?.message || 'The answer could not be graded. Try again.',
      }));
    }
  } finally {
    setSubmittingQuestion(null);
  }
};
```

In the render, use the server result instead of the answer key:

```tsx
const result = attemptResults[q.questionId];
const isSubmitted = Boolean(result);
const isCorrect = result?.isCorrect === true;
```

For each option:

```tsx
if (isSubmitted && result?.correctAnswer === opt) optClass = `${styles.optionBtn} ${styles.optionCorrect}`;
else if (isSubmitted && isThisSelected) optClass = `${styles.optionBtn} ${styles.optionIncorrect}`;
```

Feedback block:

```tsx
{result && (
  <div className={`${styles.feedbackBox} ${result.isCorrect ? styles.feedbackSuccess : styles.feedbackWarning}`}>
    <strong>{result.isCorrect ? '✓ Correct.' : '✕ Not quite.'}</strong> {result.feedback}
    {result.nextAction?.title ? <div>{result.nextAction.title}: {result.nextAction.reason}</div> : null}
  </div>
)}
{attemptErrors[q.questionId] && <div className={styles.feedbackWarning}>{attemptErrors[q.questionId]}</div>}
```

Disable the submit button while `submittingQuestion === q.questionId` and label it `Checking…`.

- [ ] **Step 7: Rewrite checkpoint submission and remove fabricated completion copy**

Replace `handleTestSubmit` with an async loop that sends one server-graded attempt per question. Also call `markQuestionStarted(qId)` from `handleTestSelect` so each checkpoint question measures its own time:

```tsx
const [checkpointResult, setCheckpointResult] = useState<{
  correct: number;
  total: number;
  mastery: AttemptResult['mastery'] | null;
  nextAction: AttemptResult['nextAction'] | null;
  offline: boolean;
} | null>(null);

const handleTestSubmit = async () => {
  if (!lessonPackage?.checkpointTest?.length || !lessonPackage.lessonVersionId) return;
  setTestSubmitted(true);
  const results: AttemptResult[] = [];
  let queuedOffline = false;

  for (const q of lessonPackage.checkpointTest) {
    const selected = testAnswers[q.questionId];
    if (!selected) continue;
    const startedAt = questionStartedAt.current[q.questionId] || Date.now();
    const elapsedSeconds = Math.max(0, Math.min(1800, Math.round((Date.now() - startedAt) / 1000)));
    const payload: AttemptSubmission = {
      lessonVersionId: lessonPackage.lessonVersionId,
      questionKey: q.questionId,
      response: selected,
      hintLevel: 0,
      hintsUsed: [],
      elapsedSeconds,
      attemptKind: 'checkpoint',
      syncIdempotencyKey: `checkpoint-${lessonPackage.lessonVersionId}-${q.questionId}`,
    };
    try {
      results.push(await api.submitAttempt(payload));
    } catch (err: any) {
      if (!navigator.onLine) {
        await queueAttemptOffline({
          clientAttemptId: payload.syncIdempotencyKey!,
          lessonId,
          lessonVersionId: payload.lessonVersionId,
          questionKey: payload.questionKey,
          response: payload.response,
          hintLevel: 0,
          hintsUsed: [],
          attemptKind: 'checkpoint',
          elapsedSeconds,
        });
        queuedOffline = true;
      } else {
        setCheckpointResult({ correct: 0, total: lessonPackage.checkpointTest.length, mastery: null, nextAction: null, offline: false });
        setAttemptErrors((prev) => ({ ...prev, checkpoint: err?.message || 'The checkpoint could not be graded. Try again.' }));
        return;
      }
    }
  }

  const correct = results.filter((item) => item.isCorrect).length;
  const last = results[results.length - 1];
  setCheckpointResult({
    correct,
    total: lessonPackage.checkpointTest.length,
    mastery: last?.mastery || null,
    nextAction: last?.nextAction || null,
    offline: queuedOffline,
  });
};
```

Render the completion card from real server data:

```tsx
<div>
  <h3>
    {checkpointResult.offline
      ? 'Checkpoint saved offline'
      : `Checkpoint: ${checkpointResult.correct} of ${checkpointResult.total} correct`}
  </h3>
  {checkpointResult.offline ? (
    <p>The answers are stored on this device. Results appear after they sync.</p>
  ) : (
    <>
      <p>
        Mastery: {checkpointResult.mastery?.band || 'not enough evidence'}
        {checkpointResult.mastery ? ` — ${checkpointResult.mastery.explanation}` : ''}
      </p>
      {checkpointResult.nextAction && (
        <p>{checkpointResult.nextAction.title}: {checkpointResult.nextAction.reason}</p>
      )}
      <button onClick={() => navigate('/')}>Back to Desk</button>
    </>
  )}
</div>
```

Delete the `navigate('/teacher')` button and the plasma-membrane sentence entirely. Also delete the `api.recordStudy` call from `handleTestSubmit`; the attempt service already writes the study event.

- [ ] **Step 8: Record real reading time instead of a fixed 60 seconds**

Add a ref and flush function:

```tsx
const readingStartedAt = useRef<number | null>(null);

const flushReadingTime = useCallback(() => {
  if (!lessonPackage || !readingStartedAt.current) return;
  const seconds = Math.max(0, Math.min(1800, Math.round((Date.now() - readingStartedAt.current) / 1000)));
  readingStartedAt.current = null;
  if (seconds < 5) return;
  api.recordStudy({
    eventType: 'reading',
    pathId: pathId || undefined,
    lessonId,
    lessonTitle: lessonPackage.title,
    seconds,
  }).catch(() => undefined);
}, [lessonPackage, lessonId, pathId]);
```

Set `readingStartedAt.current = Date.now()` after a successful lesson load. Register:

```tsx
useEffect(() => {
  const onVisibility = () => {
    if (document.visibilityState === 'hidden') flushReadingTime();
  };
  document.addEventListener('visibilitychange', onVisibility);
  return () => {
    document.removeEventListener('visibilitychange', onVisibility);
    flushReadingTime();
  };
}, [flushReadingTime]);
```

Remove the fixed `seconds: 60` call from `loadLesson`.

- [ ] **Step 9: Run the tests and build**

```powershell
cd backend
.\.venv\Scripts\python -m pytest tests/test_lesson_package_redaction.py tests/test_attempt_grading.py -q
cd ..\frontend
npm run build
npx playwright test e2e/lesson_attempts.spec.ts --project=chromium
```

Expected: PASS. Lesson packages contain no answer keys, wrong answers cannot be forced correct, and the checkpoint card reports only server-returned mastery.

- [ ] **Step 10: Commit**

```bash
git add backend/app/api/v1/learning_paths.py backend/app/api/v1/attempts.py backend/app/services/attempt_service.py backend/tests/test_lesson_package_redaction.py frontend/src/services/api.ts frontend/src/pages/LessonReaderPage.tsx frontend/src/db/indexedDB.ts frontend/e2e/lesson_attempts.spec.ts
git commit -m "feat: grade learn solve test on the server and redact answer keys"
```

---

### Task 11: Scope Offline Data to the Signed-In User and Sync It with Auth

**Files:**
- Create: `frontend/src/services/session.ts`
- Modify: `frontend/src/db/indexedDB.ts`
- Modify: `frontend/src/services/syncManager.ts`
- Modify: `frontend/src/services/api.ts` (export `authHeaders`)
- Modify: `frontend/src/context/AuthContext.tsx`
- Modify: `frontend/src/components/Navigation.tsx`
- Modify: `frontend/src/pages/HomePage.tsx`
- Modify: `frontend/src/pages/LessonReaderPage.tsx`
- Modify: `frontend/src/pages/OfflineLibraryPage.tsx`
- Modify: `frontend/src/pages/DoubtQueuePage.tsx`
- Create: `frontend/e2e/offline_sync.spec.ts`

**Interfaces:**
- Consumes: `POST /attempts` with `syncIdempotencyKey`; `POST /sync/doubts`.
- Produces: every Dexie record carries `ownerId`; `getActiveUserId()`, `setActiveUserId(id)`, `clearActiveUserId()`; `clearOfflineData()`; `syncManager.syncPendingData()` only reads and writes records for the active user, sends `Authorization`, and applies each attempt once.

- [ ] **Step 1: Write the failing offline-sync E2E test**

```ts
// frontend/e2e/offline_sync.spec.ts
import { test, expect } from '@playwright/test';

const student = {
  id: '33333333-3333-4333-8333-333333333333',
  email: 'student@example.com', role: 'student', displayName: 'Offline Student',
  grade: 9, boardId: 'board-cbse', onboardingCompleted: true, tourCompleted: true,
};

const lessonPackage = {
  lessonId: 'lesson-1', lessonVersionId: '11111111-1111-4111-8111-111111111111',
  pathId: '22222222-2222-4222-8222-222222222222', title: 'Cell Structure',
  grade: 9, subjectId: 'subject-science', objectives: [], blocks: [], visuals: [],
  workedExamples: [], takeaways: [], checkpointTest: [],
  practice: [{
    questionId: 'q1', type: 'multiple_choice', prompt: 'Which is the basic unit of life?',
    options: ['Cell', 'Tissue'], conceptIds: ['concept-cell'],
    hints: [], feedback: 'The cell is the basic unit.',
  }],
};

async function signIn(page: import('@playwright/test').Page) {
  await page.addInitScript(() => {
    localStorage.setItem('setu_auth_token', 'e2e-token');
    localStorage.setItem('setu_active_user_id', '33333333-3333-4333-8333-333333333333');
  });
  await page.route(/\/api\/v1\/profile$/, (route) => route.fulfill({ json: student }));
  await page.route('**/api/v1/learning-paths/lessons/**', (route) => route.fulfill({ json: lessonPackage }));
}

async function readAttempts(page: import('@playwright/test').Page) {
  return page.evaluate(async () => {
    const request = indexedDB.open('SetuDeskDB');
    const database = await new Promise<IDBDatabase>((resolve, reject) => {
      request.onsuccess = () => resolve(request.result);
      request.onerror = () => reject(request.error);
    });
    const transaction = database.transaction('offlineAttempts', 'readonly');
    const getAll = transaction.objectStore('offlineAttempts').getAll();
    const rows = await new Promise<any[]>((resolve, reject) => {
      getAll.onsuccess = () => resolve(getAll.result);
      getAll.onerror = () => reject(getAll.error);
    });
    database.close();
    return rows;
  });
}

test('offline attempt is owned by the user and syncs once with auth', async ({ page, context }) => {
  await signIn(page);
  let allowSync = false;
  const requests: Array<{ authorization: string | null; body: any }> = [];
  await page.route('**/api/v1/attempts', async (route) => {
    if (!allowSync) return route.abort('internetdisconnected');
    const request = route.request();
    requests.push({ authorization: request.headers()['authorization'] || null, body: request.postDataJSON() });
    await route.fulfill({
      json: {
        attemptId: 'att-1', isCorrect: true, score: 1, correctAnswer: 'Cell', feedback: 'Correct.',
        mastery: { band: 'not_enough_evidence', score: 1, evidenceCount: 1, explanation: 'One observation.' },
        nextAction: { action: 'practice_more', title: 'Practice more', reason: 'One observation is not enough.', canAdvance: true },
        alreadyRecorded: false,
      },
    });
  });

  await page.goto('/lesson/lesson-1?pathId=22222222-2222-4222-8222-222222222222');
  await context.setOffline(true);
  await page.getByRole('button', { name: /2\. Solve/ }).click();
  await page.getByRole('button', { name: 'A. Cell' }).click();
  await page.getByRole('button', { name: 'Check Answer' }).click();
  await expect(page.getByText(/Saved offline/)).toBeVisible();

  const queued = await readAttempts(page);
  expect(queued).toHaveLength(1);
  expect(queued[0].ownerId).toBe(student.id);
  expect(queued[0].lessonVersionId).toBe(lessonPackage.lessonVersionId);
  expect(queued[0].questionKey).toBe('q1');
  expect(queued[0].synced).toBe(false);

  allowSync = true;
  await context.setOffline(false);
  await page.getByRole('button', { name: 'Sync now' }).click();
  await expect.poll(() => requests.length).toBe(1);
  expect(requests[0].authorization).toBe('Bearer e2e-token');
  expect(requests[0].body.syncIdempotencyKey).toBe(queued[0].clientAttemptId);
  expect(requests[0].body.isCorrect).toBeUndefined();

  await expect.poll(async () => (await readAttempts(page))[0]?.synced).toBe(true);
  await page.getByRole('button', { name: 'Sync now' }).click().catch(() => undefined);
  await page.waitForTimeout(300);
  expect(requests).toHaveLength(1);
});

test('switching accounts clears the previous offline cache', async ({ page }) => {
  await signIn(page);
  await page.goto('/lesson/lesson-1?pathId=22222222-2222-4222-8222-222222222222');
  await page.getByRole('button', { name: /Save Offline/ }).click();
  await expect(page.getByRole('button', { name: /Saved Offline/ })).toBeVisible();

  await page.evaluate(() => {
    localStorage.setItem('setu_auth_token', 'e2e-token-b');
    localStorage.setItem('setu_active_user_id', '44444444-4444-4444-8444-444444444444');
  });
  await page.unroute(/\/api\/v1\/profile$/);
  await page.route(/\/api\/v1\/profile$/, (route) => route.fulfill({
    json: { ...student, id: '44444444-4444-4444-8444-444444444444', displayName: 'Second Student' },
  }));
  await page.goto('/library');
  await expect(page.getByText('No offline lessons downloaded yet')).toBeVisible();
});
```

- [ ] **Step 2: Run and confirm failure**

```powershell
cd frontend
npm run build
npx playwright test e2e/offline_sync.spec.ts --project=chromium
```

Expected: FAIL — records have no `ownerId`, the sync request has no `Authorization`, and the second account can still see the first account's downloaded lesson.

- [ ] **Step 3: Add the session key and upgrade the Dexie schema**

Create `frontend/src/services/session.ts`:

```ts
export const ACTIVE_USER_KEY = 'setu_active_user_id';

export function getActiveUserId(): string | null {
  return localStorage.getItem(ACTIVE_USER_KEY);
}

export function setActiveUserId(userId: string): void {
  localStorage.setItem(ACTIVE_USER_KEY, userId);
}

export function clearActiveUserId(): void {
  localStorage.removeItem(ACTIVE_USER_KEY);
}
```

In `indexedDB.ts`, add `ownerId: string` to `OfflineLesson`, `OfflineAttempt`, `OfflineDoubt`, and `CachedAnswer`. Add `syncError?: string` to `OfflineAttempt`. Replace the version block with:

```ts
this.version(2).stores({
  lessons: 'lessonId, ownerId, pathId, grade, subjectId, downloadedAt, lastAccessedAt',
  offlineVisuals: 'visualId, lessonId, type',
  offlineAttempts: 'clientAttemptId, ownerId, lessonId, questionKey, synced, submittedAt',
  doubtOutbox: 'clientDoubtId, ownerId, pathId, status, synced, submittedAt',
  cachedAnswers: 'clientDoubtId, ownerId, doubtId, cachedAt',
  syncEvents: 'eventId, eventType, synced, timestamp'
}).upgrade(async (tx) => {
  await tx.table('lessons').clear();
  await tx.table('offlineVisuals').clear();
  await tx.table('offlineAttempts').clear();
  await tx.table('doubtOutbox').clear();
  await tx.table('cachedAnswers').clear();
  await tx.table('syncEvents').clear();
});
```

Clearing legacy rows is deliberate: they have no owner and cannot be attributed safely.

- [ ] **Step 4: Require `ownerId` in every offline helper**

Change the signatures and remove all fallbacks:

```ts
export async function saveLessonOffline(lessonPackage: any, ownerId: string): Promise<void> {
  if (!ownerId) throw new Error('Sign in before saving a lesson offline.');
  if (!lessonPackage.lessonId || !lessonPackage.pathId || !lessonPackage.grade || !lessonPackage.subjectId) {
    throw new Error('This lesson package is incomplete and cannot be saved offline.');
  }
  // store ownerId; do not use 'default-path', 8, or 'GENERAL'
}

export async function getOfflineLesson(ownerId: string, lessonId: string): Promise<OfflineLesson | undefined> {
  const lesson = await db.lessons.get(lessonId);
  if (!lesson || lesson.ownerId !== ownerId) return undefined;
  await db.lessons.update(lessonId, { lastAccessedAt: new Date().toISOString() });
  return lesson;
}

export async function listOfflineLessons(ownerId: string): Promise<OfflineLesson[]> {
  return db.lessons.where('ownerId').equals(ownerId).reverse().sortBy('downloadedAt');
}

export async function deleteOfflineLesson(ownerId: string, lessonId: string): Promise<void> {
  const lesson = await db.lessons.get(lessonId);
  if (!lesson || lesson.ownerId !== ownerId) return;
  await db.transaction('rw', db.lessons, db.offlineVisuals, async () => {
    await db.lessons.delete(lessonId);
    await db.offlineVisuals.where('lessonId').equals(lessonId).delete();
  });
}

export async function getOfflineStorageUsage(ownerId: string): Promise<{ count: number; totalBytes: number }> {
  const lessons = await db.lessons.where('ownerId').equals(ownerId).toArray();
  return { count: lessons.length, totalBytes: lessons.reduce((sum, lesson) => sum + (lesson.sizeBytes || 0), 0) };
}

export async function clearOfflineData(): Promise<void> {
  await db.transaction(
    'rw',
    [db.lessons, db.offlineVisuals, db.offlineAttempts, db.doubtOutbox, db.cachedAnswers, db.syncEvents],
    async () => {
      await Promise.all([
        db.lessons.clear(), db.offlineVisuals.clear(), db.offlineAttempts.clear(),
        db.doubtOutbox.clear(), db.cachedAnswers.clear(), db.syncEvents.clear(),
      ]);
    }
  );
}
```

`queueDoubtOffline` and `queueAttemptOffline` accept `ownerId` and throw if it is missing. `getAllDoubts(ownerId)` and `listPendingDoubts(ownerId)` filter by owner. Remove the unused `syncEvents` helper if nothing writes to it.

- [ ] **Step 5: Make the session own the cache**

In `api.ts`, export the header helper:

```ts
export function authHeaders(): Record<string, string> {
  const token = localStorage.getItem('setu_auth_token');
  return token ? { Authorization: `Bearer ${token}` } : {};
}
```

In `AuthContext.tsx`, use `session.ts`:

```ts
const applySession = async (accessToken: string, profile: UserProfileData) => {
  const previous = getActiveUserId();
  if (previous && previous !== profile.id) {
    await clearOfflineData();
  }
  localStorage.setItem('setu_auth_token', accessToken);
  setActiveUserId(profile.id);
  setToken(accessToken);
  setUser(profile);
};
```

Use `applySession` in `login` and `signup`. In `loadUser`, after `getProfile()`:

```ts
const active = getActiveUserId();
if (active && active !== profile.id) await clearOfflineData();
setActiveUserId(profile.id);
setUser(profile);
```

Change `logout` to:

```ts
const logout = async () => {
  await clearOfflineData();
  localStorage.removeItem('setu_auth_token');
  clearActiveUserId();
  setToken(null);
  setUser(null);
};
```

Update the context type to `logout: () => Promise<void>`. In `Navigation.tsx`, call `void logout()`.

- [ ] **Step 6: Rewrite the sync manager**

`syncManager` must read `getActiveUserId()` once at the start; if it is null, return zeros. Replace both pending queries with owner filters. Send `Authorization` on every request:

```ts
const headers = { 'Content-Type': 'application/json', ...authHeaders() };
```

For attempts, post one record at a time to `/api/v1/attempts`:

```ts
const response = await fetch('/api/v1/attempts', {
  method: 'POST',
  headers,
  body: JSON.stringify({
    lessonVersionId: attempt.lessonVersionId,
    questionKey: attempt.questionKey,
    response: attempt.response,
    hintLevel: attempt.hintLevel,
    hintsUsed: attempt.hintsUsed,
    elapsedSeconds: attempt.elapsedSeconds,
    attemptKind: attempt.attemptKind,
    syncIdempotencyKey: attempt.clientAttemptId,
  }),
});
if (response.ok) {
  await db.offlineAttempts.update(attempt.clientAttemptId, { synced: true, syncError: undefined });
  syncedAttempts += 1;
} else if (response.status >= 400 && response.status < 500 && ![401, 429].includes(response.status)) {
  const detail = await response.json().catch(() => ({}));
  await db.offlineAttempts.update(attempt.clientAttemptId, {
    syncError: typeof detail.detail === 'string' ? detail.detail : `Rejected (${response.status})`,
  });
}
```

For doubts, send `/api/v1/sync/doubts` with the same headers and mark a local doubt `synced: true` only when the server returns `answered`. When the server returns `needs_retry`, keep `synced: false`, set `status: 'queued'`, and store `lastError`. Do not count it as synced.

Update `notify()` to count only the active user's `!synced` records. Add a public `refreshPending()` that calls `notify()`; call it from `queueAttemptOffline` and `queueDoubtOffline` is not possible without a circular import, so call `syncManager.refreshPending()` from the page after queueing.

- [ ] **Step 7: Update every call site**

- `HomePage.tsx`: `saveLessonOffline(pkg, user.id)`.
- `LessonReaderPage.tsx`: use `const { user } = useAuth();` and pass `user.id` to `getOfflineLesson`, `saveLessonOffline`, `queueDoubtOffline`, and `queueAttemptOffline`; call `syncManager.refreshPending()` after queueing.
- `OfflineLibraryPage.tsx`: read the signed-in user; `listOfflineLessons(user.id)`, `getOfflineStorageUsage(user.id)`, `deleteOfflineLesson(user.id, lessonId)`.
- `DoubtQueuePage.tsx`: `getAllDoubts(user.id)`.
- `Navigation.tsx`: label the sync button `Sync now`; render it whenever there are pending records and the browser is online.

- [ ] **Step 8: Run the tests**

```powershell
cd frontend
npm run build
npx playwright test e2e/offline_sync.spec.ts --project=chromium
cd ..\backend
.\.venv\Scripts\python -m pytest tests/test_attempt_grading.py -q
```

Expected: PASS. The queued attempt belongs to the signed-in user, syncs with a bearer token exactly once, and a second account sees an empty offline library.

- [ ] **Step 9: Commit**

```bash
git add frontend/src/services/session.ts frontend/src/db/indexedDB.ts frontend/src/services/syncManager.ts frontend/src/services/api.ts frontend/src/context/AuthContext.tsx frontend/src/components/Navigation.tsx frontend/src/pages/HomePage.tsx frontend/src/pages/LessonReaderPage.tsx frontend/src/pages/OfflineLibraryPage.tsx frontend/src/pages/DoubtQueuePage.tsx frontend/e2e/offline_sync.spec.ts
git commit -m "fix: scope offline data per user and authenticate sync"
```

---

### Task 12: Make Online Doubts Truthful and Offline Doubts Retryable

**Files:**
- Modify: `backend/app/services/sync_service.py`
- Modify: `backend/app/api/v1/doubts.py`
- Modify: `backend/app/api/v1/sync.py`
- Modify: `backend/tests/test_idempotent_sync.py` (remove the Task 1 temporary skip)
- Modify: `frontend/src/pages/LessonReaderPage.tsx`
- Modify: `frontend/src/pages/DoubtQueuePage.tsx`
- Create: `backend/tests/test_doubt_truth.py`
- Create: `frontend/e2e/doubt_truth.spec.ts`

**Interfaces:**
- Consumes: `retrieval_service.hybrid_search`, `ai_provider.generate_chat`, `Doubt`.
- Produces: `sync_doubt` retries an existing `needs_retry` record instead of returning it forever; provider failures return `status="needs_retry"` with `answerJson.retryable=true` and no answer; only a real browser-offline event queues a doubt; the drawer and history page show answered, retryable, and insufficient-evidence states distinctly.

- [ ] **Step 1: Write the failing backend tests**

```python
# backend/tests/test_doubt_truth.py
import uuid

import pytest

from app.models.doubts import Doubt
from app.services import sync_service as sync_module
from app.services.sync_service import sync_service


def _evidence():
    return {
        "results": [{
            "citationId": "cite_1", "pageStart": 1, "pageEnd": 1,
            "headingPath": ["Chapter 1"], "text": "Cells are the basic unit of life.",
        }],
        "insufficient_evidence": False,
    }


@pytest.mark.asyncio
async def test_provider_failure_is_retryable_then_answered(db, monkeypatch):
    owner_id = uuid.uuid4()
    calls = {"count": 0}

    async def fake_search(**kwargs):
        return _evidence()

    async def flaky_chat(**kwargs):
        calls["count"] += 1
        if calls["count"] == 1:
            raise RuntimeError("provider offline")
        return "Cells are the basic unit of life."

    monkeypatch.setattr(sync_module.retrieval_service, "hybrid_search", fake_search)
    monkeypatch.setattr(sync_module.ai_provider, "generate_chat", flaky_chat)

    first = await sync_service.sync_doubt(
        db=db, owner_id=owner_id, client_doubt_id="doubt-1",
        question_text="What is a cell?",
    )
    assert first["status"] == "needs_retry"
    assert first["answerJson"]["retryable"] is True
    assert first["answerJson"]["answer"] is None
    assert db.query(Doubt).filter(Doubt.owner_id == owner_id).count() == 1

    second = await sync_service.sync_doubt(
        db=db, owner_id=owner_id, client_doubt_id="doubt-1",
        question_text="What is a cell?",
    )
    assert second["status"] == "answered"
    assert second["alreadyExisted"] is True
    assert "basic unit" in second["answerJson"]["answer"]
    assert len(second["answerJson"]["citations"]) == 1


@pytest.mark.asyncio
async def test_insufficient_evidence_is_answered_without_citations(db, monkeypatch):
    owner_id = uuid.uuid4()

    async def fake_search(**kwargs):
        return {"results": [], "insufficient_evidence": True}

    monkeypatch.setattr(sync_module.retrieval_service, "hybrid_search", fake_search)

    result = await sync_service.sync_doubt(
        db=db, owner_id=owner_id, client_doubt_id="doubt-2",
        question_text="What is photosynthesis?",
    )
    assert result["status"] == "answered"
    assert result["answerJson"]["citations"] == []
    assert result["answerJson"]["limitations"] == "insufficient_source_evidence"
    assert "does not contain sufficient verified evidence" in result["answerJson"]["answer"]


def test_blank_question_is_rejected(client):
    response = client.post(
        "/api/v1/doubts",
        headers={"X-User-Id": str(uuid.uuid4())},
        json={"clientDoubtId": "doubt-3", "questionText": "   "},
    )
    assert response.status_code == 422
```

- [ ] **Step 2: Write the failing doubt UI E2E test**

```ts
// frontend/e2e/doubt_truth.spec.ts
import { test, expect } from '@playwright/test';

const profile = {
  id: '33333333-3333-4333-8333-333333333333', email: 'student@example.com',
  role: 'student', displayName: 'Doubt Student', grade: 9,
  boardId: 'board-cbse', onboardingCompleted: true, tourCompleted: true,
};

const lessonPackage = {
  lessonId: 'lesson-1', lessonVersionId: '11111111-1111-4111-8111-111111111111',
  pathId: '22222222-2222-4222-8222-222222222222', title: 'Cell Structure',
  grade: 9, subjectId: 'subject-science', objectives: [], practice: [], checkpointTest: [],
  blocks: [{ blockId: 'b1', heading: 'The Cell', content: 'Cells are the basic unit.', sourceRefs: [{ pageStart: 1 }] }],
  visuals: [], workedExamples: [], takeaways: [],
};

async function openDoubt(page: import('@playwright/test').Page) {
  await page.addInitScript(() => {
    localStorage.setItem('setu_auth_token', 'e2e-token');
    localStorage.setItem('setu_active_user_id', '33333333-3333-4333-8333-333333333333');
  });
  await page.route(/\/api\/v1\/profile$/, (route) => route.fulfill({ json: profile }));
  await page.route('**/api/v1/learning-paths/lessons/**', (route) => route.fulfill({ json: lessonPackage }));
  await page.goto('/lesson/lesson-1?pathId=22222222-2222-4222-8222-222222222222');
  await page.getByRole('button', { name: /Ask Doubt/ }).click();
  await page.getByPlaceholder(/Ask any question/).fill('What is a cell?');
}

test('an online provider failure is retryable and never called queued', async ({ page }) => {
  await openDoubt(page);
  let call = 0;
  await page.route('**/api/v1/doubts', async (route) => {
    call += 1;
    if (call === 1) {
      await route.fulfill({
        status: 503,
        json: { detail: 'The tutor is unavailable. Your question was saved; retry in a moment.' },
      });
      return;
    }
    await route.fulfill({
      json: {
        id: 'doubt-1', status: 'answered',
        answerJson: { answer: 'A cell is the basic unit of life.', citations: [{ pageStart: 1 }], limitations: null },
      },
    });
  });

  await page.getByRole('button', { name: 'Submit Doubt' }).click();
  await expect(page.getByText('The tutor is unavailable. Your question was saved; retry in a moment.')).toBeVisible();
  await expect(page.getByText(/Stored in Offline Queue/)).toHaveCount(0);
  await page.getByRole('button', { name: 'Retry' }).click();
  await expect(page.getByText('A cell is the basic unit of life.')).toBeVisible();
  expect(call).toBe(2);
});

test('a doubt is queued only when the browser is offline', async ({ page, context }) => {
  await openDoubt(page);
  await context.setOffline(true);
  await page.getByRole('button', { name: 'Submit Doubt' }).click();
  await expect(page.getByText(/Stored in Offline Queue/)).toBeVisible();
});

test('history marks a needs-retry doubt and allows retry', async ({ page }) => {
  await page.addInitScript(() => {
    localStorage.setItem('setu_auth_token', 'e2e-token');
    localStorage.setItem('setu_active_user_id', '33333333-3333-4333-8333-333333333333');
  });
  await page.route(/\/api\/v1\/profile$/, (route) => route.fulfill({ json: profile }));
  let call = 0;
  await page.route('**/api/v1/doubts', async (route) => {
    if (route.request().method() === 'GET') {
      await route.fulfill({ json: [{
        id: 'doubt-1', clientDoubtId: 'doubt-1', status: 'needs_retry',
        questionText: 'What is a cell?', answerJson: null, createdAt: new Date().toISOString(),
      }] });
      return;
    }
    call += 1;
    await route.fulfill({ json: {
      id: 'doubt-1', status: 'answered',
      answerJson: { answer: 'A cell is the basic unit of life.', citations: [], limitations: null },
    } });
  });

  await page.goto('/doubts');
  await expect(page.getByText('Needs retry')).toBeVisible();
  await page.getByRole('button', { name: 'Retry' }).click();
  await expect(page.getByText('A cell is the basic unit of life.')).toBeVisible();
  expect(call).toBe(1);
});
```

- [ ] **Step 3: Run and confirm failure**

```powershell
cd backend
.\.venv\Scripts\python -m pytest tests/test_doubt_truth.py -q
cd ..\frontend
npm run build
npx playwright test e2e/doubt_truth.spec.ts --project=chromium
```

Expected: FAIL — a `needs_retry` doubt is returned forever, blank questions are accepted, and online provider errors are labelled as offline queue entries.

- [ ] **Step 4: Make `sync_doubt` retry rather than replay a failure**

Replace the existing-record branch:

```python
if existing:
    if existing.status == "answered":
        return {
            "id": str(existing.id),
            "clientDoubtId": existing.client_doubt_id,
            "status": existing.status,
            "questionText": existing.question_text,
            "answerJson": existing.answer_json,
            "alreadyExisted": True,
        }
    doubt = existing
else:
    doubt = Doubt(
        owner_id=owner_id,
        client_doubt_id=client_doubt_id,
        path_id=path_id,
        lesson_version_id=lesson_version_id,
        block_id=block_id,
        source_page=source_page,
        question_text=question_text,
        status="processing",
        submitted_at=datetime.datetime.utcnow(),
    )
    db.add(doubt)
    db.flush()
```

Create or reuse the doubt row with `status="processing"` and `db.flush()` before retrieval, then put retrieval, the insufficient-evidence branch, and the chat call inside one `try/except Exception` so every failure path persists a retryable record. On any retrieval, embedding, or provider failure set:

```python
except Exception:
    doubt.status = "needs_retry"
    doubt.last_error_code = "tutor_unavailable"
    doubt.answer_json = {
        "answer": None,
        "citations": [],
        "limitations": "tutor_unavailable",
        "retryable": True,
        "message": "The tutor is unavailable. Your question is saved; retry in a moment.",
    }
    doubt.answered_at = None
```

Do not let a retrieval or embedding exception escape before the doubt row exists. On success:

```python
doubt.status = "answered"
doubt.last_error_code = None
doubt.answer_json = answer_payload
doubt.answered_at = datetime.datetime.utcnow()
```

Remove the temporary module-level `pytestmark = pytest.mark.skip(...)` from `backend/tests/test_idempotent_sync.py`. With retryable failures, that test must run against the disposable database without requiring a live model.

Commit and return the same payload shape, including `alreadyExisted`. Set `already_existed = existing is not None` and return that value, so a retried `needs_retry` record still reports `alreadyExisted: True`. Never store `str(exception)` in a field the student can read.

- [ ] **Step 5: Validate doubt input and keep the batch endpoint honest**

In `doubts.py`:

```python
from pydantic import BaseModel, Field

class DoubtSubmission(BaseModel):
    clientDoubtId: str = Field(min_length=1, max_length=100)
    questionText: str = Field(min_length=3, max_length=2000)
    pathId: Optional[str] = None
    lessonVersionId: Optional[str] = None
    blockId: Optional[str] = None
    sourcePage: Optional[int] = Field(default=None, ge=1)
```

Add `lastErrorCode` and `lessonVersionId` to `list_user_doubts`.

In `sync.py`, skip malformed items with a per-item `rejected` result instead of calling the service with `None`:

```python
client_doubt_id = d.get("clientDoubtId")
question_text = str(d.get("questionText") or "").strip()
if not client_doubt_id or len(question_text) < 3:
    results.append({
        "clientDoubtId": client_doubt_id,
        "status": "rejected",
        "error": "clientDoubtId and a question of at least 3 characters are required.",
    })
    continue
```

Delete the `/sync/batch` route and `sync_batch_events` from `sync_service.py`. It records events as "applied" without applying attempts or evidence and is no longer called. Keep the `sync_events` table for historical compatibility; do not create new rows.

- [ ] **Step 6: Split online failure, retryable failure, and offline queue in the drawer**

Add `const [lastDoubtPayload, setLastDoubtPayload] = useState<...>(null);` and a `submitDoubt(payload)` function. The handler must follow this order:

1. `if (!navigator.onLine)` → `queueDoubtOffline({ ...payload, ownerId: user.id })`, show `queued`, return.
2. Call `api.askDoubt(payload)`.
3. If `res.status === 'answered'` and `res.answerJson?.answer` → show answer, citations, and `limitations`.
4. If `res.status === 'needs_retry'` or `!res.answerJson?.answer` → show `failed` with `retryable: true`, message from `answerJson.message` or "The tutor could not answer. Try again.", and a **Retry** button that calls `submitDoubt(lastDoubtPayload)`.
5. On `TypeError` while online → show "Could not reach SETU. Check your connection and try again." with Retry. **Do not queue.**
6. On any other error → show the server message with Retry. **Do not queue.**

The queued path must be reachable only from step 1. Label the answer "Answer from your sources"; if `limitations === 'insufficient_source_evidence'`, show "The uploaded source does not contain enough evidence for a verified answer."

- [ ] **Step 7: Make the doubts page show real states and retry**

In `DoubtQueuePage.tsx`:

- Title: `Doubts`; copy: "Your questions and their status. Questions asked offline sync when you reconnect."
- Map `answered` → Answered, `needs_retry` → Needs retry, `queued_offline` → Waiting to sync, `rejected` → Rejected.
- Add a Retry button for `needs_retry` and `rejected` that calls `api.askDoubt` with the same `clientDoubtId` and question text, then reloads.
- Show `limitations` under the answer; do not label every answer "Verified textbook answer".
- Empty state: "No doubts yet." with a link to the Desk.

- [ ] **Step 8: Run the tests**

```powershell
cd backend
.\.venv\Scripts\python -m pytest tests/test_doubt_truth.py tests/test_idempotent_sync.py -q
cd ..\frontend
npm run build
npx playwright test e2e/doubt_truth.spec.ts --project=chromium
```

Expected: PASS. A provider failure is retryable, the same client ID is reused, insufficient evidence is explicit, and only a real offline browser queues.

- [ ] **Step 9: Commit**

```bash
git add backend/app/services/sync_service.py backend/app/api/v1/doubts.py backend/app/api/v1/sync.py backend/tests/test_doubt_truth.py backend/tests/test_idempotent_sync.py frontend/src/pages/LessonReaderPage.tsx frontend/src/pages/DoubtQueuePage.tsx frontend/e2e/doubt_truth.spec.ts
git commit -m "fix: make doubts retryable and reserve offline queue for real offline"
```

### Task 13: Make the Student Dashboard and Study Summary Tell the Truth

**Files:**
- Modify: `backend/app/api/v1/profile.py`
- Modify: `backend/app/api/v1/study.py`
- Modify: `frontend/src/services/api.ts`
- Modify: `frontend/src/pages/StudentDashboardPage.tsx`
- Modify: `frontend/src/pages/StudentDashboardPage.module.css`
- Modify: `frontend/src/pages/HomePage.tsx`
- Create: `backend/tests/test_student_dashboard_truth.py`
- Create: `frontend/e2e/student_dashboard_truth.spec.ts`

**Interfaces:**
- Consumes: `UserProfile`, `StudyEvent`, `QuizAttempt`, `ConceptMasterySnapshot`, `GET /catalogue/boards`.
- Produces: `GET /profile/dashboard` returns `404` when no profile exists; `GET /profile` and `PUT /profile` return `404` instead of creating a profile; dashboard time comes only from `study_events`; `recentAttempts[].elapsedSeconds` is the stored value or `0`; `summarize_student` returns `pace: None` and `dailyGoalMinutes: None` when unset; `api.getBoards()` is available to every settings form.

- [ ] **Step 1: Write the failing backend tests**

```python
# backend/tests/test_student_dashboard_truth.py
import datetime
import uuid

from app.models.learning import (
    LearningPath, PathLesson, LessonVersion, Question, QuizAttempt, StudyEvent,
)
from app.models.profiles import UserProfile
from tests.conftest import auth_headers


def _student(db, name="Asha"):
    user_id = uuid.uuid4()
    db.add(UserProfile(id=user_id, email=f"{name.lower()}@example.com", display_name=name, role="student"))
    db.commit()
    return user_id


def test_dashboard_and_profile_require_a_real_row(client, db):
    stranger = uuid.uuid4()
    assert client.get("/api/v1/profile/dashboard", headers=auth_headers(stranger)).status_code == 404
    assert client.get("/api/v1/profile", headers=auth_headers(stranger)).status_code == 404
    assert client.put(
        "/api/v1/profile", headers=auth_headers(stranger), json={"displayName": "Invented"}
    ).status_code == 404


def test_fresh_student_dashboard_has_no_invented_history(client, db):
    student_id = _student(db)
    response = client.get("/api/v1/profile/dashboard", headers=auth_headers(student_id))
    assert response.status_code == 200
    data = response.json()

    assert data["profile"]["grade"] is None
    assert data["profile"]["boardId"] is None
    assert data["profile"]["dailyGoalMinutes"] is None
    assert data["stats"] == {
        "currentStreak": 0,
        "longestStreak": 0,
        "totalMinutesStudied": 0.0,
        "totalSessions": 0,
        "averageAccuracy": 0.0,
        "totalQuestionsAttempted": 0,
    }
    assert len(data["activityHeatmap"]) == 84
    assert all(day["minutes"] == 0 and day["level"] == 0 for day in data["activityHeatmap"])
    assert data["conceptMastery"] == []
    assert data["recentAttempts"] == []
    assert data["classrooms"] == []


def test_attempt_time_is_not_added_to_study_time_twice(client, db):
    student_id = _student(db)
    db.add(StudyEvent(owner_id=student_id, event_type="reading", seconds=120))
    path = LearningPath(owner_id=student_id, grade=9, subject_id="subject-science", outline_json={"title": "Cells"})
    db.add(path)
    db.flush()
    lesson = PathLesson(path_id=path.id, lesson_key="lesson_1", title="Cells", sequence=1)
    db.add(lesson)
    db.flush()
    version = LessonVersion(path_lesson_id=lesson.id, lesson_package_json={"title": "Cells"}, validation_status="ready")
    db.add(version)
    db.flush()
    question = Question(
        lesson_version_id=version.id, question_key="q1", type="multiple_choice",
        prompt_json={"prompt": "Which unit?"}, answer_key_json={"correct": "Cell"}, concept_ids=["concept-cell"],
    )
    db.add(question)
    db.flush()
    db.add(QuizAttempt(
        owner_id=student_id, question_id=question.id, lesson_version_id=version.id,
        response_json={"answer": "Cell"}, score=1.0, is_correct=True, elapsed_seconds=75,
    ))
    db.commit()

    data = client.get("/api/v1/profile/dashboard", headers=auth_headers(student_id)).json()
    assert data["stats"]["totalMinutesStudied"] == 2.0
    assert data["stats"]["totalSessions"] == 1
    assert data["recentAttempts"][0]["elapsedSeconds"] == 75
    today = datetime.datetime.utcnow().date().isoformat()
    today_row = next(day for day in data["activityHeatmap"] if day["date"] == today)
    assert today_row["minutes"] == 2.0


def test_duplicate_profile_study_event_route_is_removed(client, db):
    student_id = _student(db)
    response = client.post(
        "/api/v1/profile/study-event",
        headers=auth_headers(student_id),
        json={"eventType": "reading", "seconds": 60},
    )
    assert response.status_code == 404


def test_study_summary_does_not_invent_a_pace_or_goal(client, db):
    student_id = _student(db)
    summary = client.get("/api/v1/study/summary", headers=auth_headers(student_id)).json()
    assert summary["pace"] is None
    assert summary["dailyGoalMinutes"] is None
    assert "25" not in summary["focus"]
    assert summary["minutesStudied"] == 0.0
```

- [ ] **Step 2: Run and confirm failure**

```powershell
.\.venv\Scripts\python -m pytest tests/test_student_dashboard_truth.py -q
```

Expected: FAIL — missing profiles are created with `grade=10`/`9` and `board-cbse`, attempts are added to study time twice, the duplicate route still exists, and the summary invents a 25-minute pace.

- [ ] **Step 3: Remove profile fabrication and double-counted time**

In `profile.py`:

```python
profile = db.query(UserProfile).filter(UserProfile.id == user_id).first()
if not profile:
    raise HTTPException(status_code=404, detail="Profile not found. Complete signup or onboarding.")
```

Apply the same `404` in `get_profile` and `update_profile`; never construct a `UserProfile` in a read or update request. Delete `StudyEventLogRequest` and the entire `POST /profile/study-event` route. `/study/events` is the only study-time writer.

In `get_student_dashboard`:

- Delete the loop that adds `att.elapsed_seconds` to `daily_stats`. The attempt service already writes a `StudyEvent`, so the heatmap must read `study_events` only.
- Set `total_sessions = len(events)`.
- Return `"elapsedSeconds": att.elapsed_seconds if att.elapsed_seconds is not None else 0`.
- Add `"academicContextComplete": bool(profile.grade and profile.board_id and profile.preferred_language)` beside the profile fields.
- Keep `averageAccuracy` as `0.0` when no attempts exist; the UI decides how to label the absence of evidence.

In `study.py` `summarize_student`:

```python
pace_minutes = profile.daily_goal_minutes if profile and profile.daily_goal_minutes else None
pace = None
if profile and isinstance(profile.accessibility_preferences, dict):
    pace = profile.accessibility_preferences.get("pace")

if improvement == "needs_support":
    focus = "Stay with the current unit and retry the check before opening the next one."
elif improvement == "improving":
    focus = "Recent checks are stronger than earlier ones. Continue into the next ready unit."
elif pace and pace_minutes:
    focus = f"Your pace is {pace_minutes} minutes a day. Work through the ready units in order."
elif pace_minutes:
    focus = f"Your daily goal is {pace_minutes} minutes. Work through the ready units in order."
elif pace:
    focus = f"Your pace is {pace}. Work through the ready units in order."
else:
    focus = "Set a daily goal and pace to get a schedule suggestion."
```

- [ ] **Step 4: Update the typed client**

In `api.ts`:

```ts
export interface UserProfileData {
  id: string;
  email: string | null;
  role: 'student' | 'teacher';
  displayName: string;
  grade?: number | null;
  boardId?: string | null;
  preferredLanguage?: string | null;
  subjectsInterested?: string[];
  learningGoals?: string[];
  dailyGoalMinutes?: number | null;
  academicContextComplete?: boolean;
  accessibilityPreferences?: {
    font_size?: string;
    reduced_motion?: boolean;
    high_contrast?: boolean;
    pace?: 'short' | 'steady' | 'long';
  };
  onboardingCompleted?: boolean;
  tourCompleted?: boolean;
}

export interface CatalogueBoard {
  id: string;
  code: string;
  name: string;
  region?: string;
  officialUrl?: string;
}

export interface RecentAttemptItem {
  id: string;
  lessonTitle: string;
  score: number;
  isCorrect: boolean;
  hintsUsed: number;
  elapsedSeconds: number;
  occurredAt: string | null;
}
```

Add:

```ts
async getBoards(): Promise<CatalogueBoard[]> {
  return request<CatalogueBoard[]>('/catalogue/boards');
},
```

Update `getStudySummary` to return `pace: string | null`, `dailyGoalMinutes: number | null`, and suggestions carrying `conceptId`, `status`, `explanation`, and `teacherName` (the backend supplies them in Task 14).

- [ ] **Step 5: Make the dashboard render only stored values**

In `StudentDashboardPage.tsx`:

- Start edit state as `editGrade: number | '' = ''`, `editBoard: string = ''`, `editGoal: number | '' = ''`, and copy from `res.profile` without `|| 10`, `|| 'board-cbse'`, or `|| 25`.
- Fetch boards once with `api.getBoards()` and render only those options. If boards fail to load, show the error and disable Save; never fall back to a hardcoded list.
- Render the class badge only when `profile.grade != null`, the board badge only when `profile.boardId`, the goal badge only when `profile.dailyGoalMinutes != null`, and the email line only when `profile.email` is non-empty. Delete the `Registered Student` fallback.
- Under the profile name, if `!profile.grade || !profile.boardId || !profile.preferredLanguage`, show:

```tsx
<div className={styles.emptyNotice}>
  Add your class, board, and language to finish setting up your desk.
  <button type="button" className={styles.editBtn} onClick={() => setIsEditOpen(true)}>
    Add academic details
  </button>
</div>
```

- Accuracy card: `stats.totalQuestionsAttempted === 0 ? '—' : `${stats.averageAccuracy}%`` and sub-copy `No checkpoint attempts yet` when zero.
- Heatmap: when `stats.totalSessions === 0`, show “No study activity yet. Open a ready lesson to start the heatmap.” and do not render an all-zero grid as if it were activity.
- Mastery: default band label `Not enough evidence`; bar width `item.score` exactly (no `Math.max(..., 8)`); empty copy “No concept mastery evidence yet. Answer a checkpoint to build evidence.”
- Recent attempts: `att.elapsedSeconds > 0 ? `${att.elapsedSeconds}s` : '—'`; empty copy “No checkpoint attempts yet.”
- Classrooms empty copy “You have not joined a classroom.” Keep the join form.
- Save sends only selected real values. If `editGrade` or `editBoard` is empty, show “Choose a class and board before saving.” and keep the modal open.

In `HomePage.tsx`, replace `studySummary?.pace || user?.accessibilityPreferences?.pace || 'steady'` with:

```tsx
const pace = studySummary?.pace || user?.accessibilityPreferences?.pace || null;
const paceLabel = pace === 'short' ? 'Short sessions' : pace === 'long' ? 'Longer sessions' : pace === 'steady' ? 'Steady pace' : 'No pace set';
```

- [ ] **Step 6: Write the dashboard E2E test**

```ts
// frontend/e2e/student_dashboard_truth.spec.ts
import { test, expect } from '@playwright/test';

const student = {
  id: '55555555-5555-4555-8555-555555555555',
  email: 'asha@example.com', role: 'student', displayName: 'Asha',
  grade: null, boardId: null, preferredLanguage: null, dailyGoalMinutes: null,
  onboardingCompleted: true, tourCompleted: true,
};

const heatmap = Array.from({ length: 84 }, (_, index) => ({
  date: `2026-08-${String((index % 28) + 1).padStart(2, '0')}`,
  seconds: 0, minutes: 0, count: 0, level: 0,
}));

test('a fresh student sees empty states, not invented class or goal values', async ({ page }) => {
  await page.addInitScript(() => {
    localStorage.setItem('setu_auth_token', 'e2e-token');
    localStorage.setItem('setu_active_user_id', '55555555-5555-4555-8555-555555555555');
  });
  await page.route('**/api/v1/profile', (route) => route.fulfill({ json: student }));
  await page.route('**/api/v1/profile/dashboard', (route) => route.fulfill({
    json: {
      profile: student,
      stats: {
        currentStreak: 0, longestStreak: 0, totalMinutesStudied: 0,
        totalSessions: 0, averageAccuracy: 0, totalQuestionsAttempted: 0,
      },
      activityHeatmap: heatmap,
      conceptMastery: [],
      recentAttempts: [],
      classrooms: [],
    },
  }));
  await page.route('**/api/v1/catalogue/boards', (route) => route.fulfill({
    json: [{ id: 'board-cbse', code: 'CBSE', name: 'Central Board of Secondary Education' }],
  }));

  await page.goto('/dashboard');
  await expect(page.getByText('Add your class, board, and language')).toBeVisible();
  await expect(page.getByText('No study activity yet.')).toBeVisible();
  await expect(page.getByText('No concept mastery evidence yet.')).toBeVisible();
  await expect(page.getByText('No checkpoint attempts yet.')).toBeVisible();
  await expect(page.getByText('Registered Student')).toHaveCount(0);
  await expect(page.getByText(/Class 10/)).toHaveCount(0);
  await expect(page.getByText(/25 min\/day/)).toHaveCount(0);
});
```

- [ ] **Step 7: Run the tests**

```powershell
cd backend
.\.venv\Scripts\python -m pytest tests/test_student_dashboard_truth.py -q
cd ..\frontend
npm run build
npx playwright test e2e/student_dashboard_truth.spec.ts --project=chromium
```

Expected: PASS. A fresh account has zeroes and empty states; a 120-second reading event plus a 75-second attempt reports 2.0 minutes and 75 seconds, not 195 seconds.

- [ ] **Step 8: Commit**

```bash
git add backend/app/api/v1/profile.py backend/app/api/v1/study.py backend/tests/test_student_dashboard_truth.py frontend/src/services/api.ts frontend/src/pages/StudentDashboardPage.tsx frontend/src/pages/StudentDashboardPage.module.css frontend/src/pages/HomePage.tsx frontend/e2e/student_dashboard_truth.spec.ts
git commit -m "fix: make student dashboard and study summary use only stored evidence"
```

---

### Task 14: Scope Teacher Evidence and Make Recommendations Explainable

**Files:**
- Modify: `backend/app/api/v1/teacher.py`
- Modify: `backend/app/api/v1/study.py`
- Modify: `frontend/src/services/api.ts`
- Modify: `frontend/src/pages/TeacherDashboardPage.tsx`
- Modify: `frontend/src/pages/TeacherDashboardPage.module.css`
- Modify: `frontend/src/pages/HomePage.tsx`
- Create: `backend/tests/test_teacher_evidence_scope.py`
- Modify: `backend/tests/test_multi_user_evidence_matrix.py` (new attempt and recommendation contracts)
- Create: `frontend/e2e/teacher_evidence.spec.ts`

**Interfaces:**
- Consumes: `Classroom`, `ClassroomMembership`, `ConceptEvidence`, `ConceptMasterySnapshot`, `TeacherAction`, `summarize_student`.
- Produces: `GET /teacher/evidence?classroomId=<uuid>` scoped to the requesting teacher’s classroom; `GET /teacher/classrooms/{id}/evidence-matrix` returns each member’s `concepts` and `evidenceBand` (including `not_enough_evidence`); `POST /teacher/recommendations` requires a real evidenced concept, stores the evidence snapshot in `reason_json`, and creates a `proposed` action; `POST /study/recommendations/{id}/respond` lets only the addressed student `accept` or `dismiss`; `GET /study/summary` returns only `proposed` suggestions with an explanation.

- [ ] **Step 1: Write the failing authorization and recommendation tests**

```python
# backend/tests/test_teacher_evidence_scope.py
import datetime
import uuid

from app.models.classroom import Classroom, ClassroomMembership, TeacherAction
from app.models.learning import ConceptEvidence, ConceptMasterySnapshot, StudyEvent
from app.models.profiles import UserProfile
from tests.conftest import auth_headers


def _profile(db, role="student", name=None):
    user_id = uuid.uuid4()
    db.add(UserProfile(
        id=user_id, email=f"{role}-{user_id.hex[:6]}@example.com",
        display_name=name or f"{role.title()} {user_id.hex[:4]}", role=role,
    ))
    db.commit()
    return user_id


def _classroom(db, teacher_id, name="Morning Science"):
    room = Classroom(
        owner_teacher_id=teacher_id, name=name, grade=9,
        board_id="board-cbse", subject_scope="subject-science",
        join_code=f"T{uuid.uuid4().hex[:5].upper()}",
    )
    db.add(room)
    db.commit()
    return room


def _member(db, room, student_id):
    db.add(ClassroomMembership(classroom_id=room.id, student_id=student_id, status="active"))
    db.commit()


def _snapshot(db, student_id, concept="concept-cell", band="demonstrated", count=3):
    db.add(ConceptMasterySnapshot(
        owner_id=student_id, concept_id=concept, estimate_band=band,
        numeric_estimate=0.9, evidence_count=count,
        calculated_at=datetime.datetime.utcnow(),
    ))
    db.commit()


def _evidence(db, student_id, concept="concept-cell", outcome="correct"):
    db.add(ConceptEvidence(owner_id=student_id, concept_id=concept, outcome=outcome))
    db.commit()


def test_teacher_sees_only_own_classroom_evidence(client, db):
    teacher_a, teacher_b = _profile(db, "teacher"), _profile(db, "teacher")
    room_a, room_b = _classroom(db, teacher_a), _classroom(db, teacher_b)
    student_a, student_b = _profile(db, name="Asha"), _profile(db, name="Bilal")
    _member(db, room_a, student_a)
    _member(db, room_b, student_b)
    _snapshot(db, student_a)
    _snapshot(db, student_b, concept="concept-secret", band="developing", count=2)
    _evidence(db, student_a, outcome="correct")
    _evidence(db, student_a, outcome="incorrect")
    _evidence(db, student_b, concept="concept-secret", outcome="incorrect")
    db.add(StudyEvent(owner_id=student_a, event_type="reading", seconds=300, lesson_title="Cells"))
    db.commit()

    response = client.get(
        f"/api/v1/teacher/classrooms/{room_a.id}/evidence-matrix",
        headers=auth_headers(teacher_a),
    )
    assert response.status_code == 200
    matrix = response.json()["matrix"]
    assert [row["studentId"] for row in matrix] == [str(student_a)]
    assert matrix[0]["studentName"] == "Asha"
    assert matrix[0]["evidenceBand"] == "demonstrated"
    assert matrix[0]["concepts"][0]["conceptId"] == "concept-cell"
    assert matrix[0]["minutesStudied"] == 5.0

    scoped = client.get(
        f"/api/v1/teacher/evidence?classroomId={room_a.id}",
        headers=auth_headers(teacher_a),
    )
    assert scoped.status_code == 200
    assert {row["conceptId"] for row in scoped.json()} == {"concept-cell"}
    assert scoped.json()[0]["totalAttempts"] == 2

    assert client.get(
        f"/api/v1/teacher/classrooms/{room_b.id}/evidence-matrix",
        headers=auth_headers(teacher_a),
    ).status_code == 404
    assert client.get(
        f"/api/v1/teacher/evidence?classroomId={room_b.id}",
        headers=auth_headers(teacher_a),
    ).status_code == 404


def test_recommendation_requires_evidence_and_is_respondable(client, db):
    teacher_id = _profile(db, "teacher")
    room = _classroom(db, teacher_id)
    student_id = _profile(db, name="Asha")
    outsider_id = _profile(db, name="Bilal")
    _member(db, room, student_id)
    _snapshot(db, student_id, band="approaching", count=2)
    student_headers = auth_headers(student_id)

    no_evidence = client.post(
        "/api/v1/teacher/recommendations",
        headers=auth_headers(teacher_id),
        json={
            "classroomId": str(room.id), "studentId": str(student_id),
            "conceptId": "concept-not-assessed", "actionType": "targeted_review",
            "notes": "Review the worked example.",
        },
    )
    assert no_evidence.status_code == 422

    created = client.post(
        "/api/v1/teacher/recommendations",
        headers=auth_headers(teacher_id),
        json={
            "classroomId": str(room.id), "studentId": str(student_id),
            "conceptId": "concept-cell", "actionType": "targeted_review",
            "notes": "Review the worked example before the next check.",
        },
    )
    assert created.status_code == 200
    payload = created.json()
    assert payload["status"] == "proposed"
    assert payload["reason"]["evidence"]["band"] == "approaching"
    assert payload["reason"]["evidence"]["evidenceCount"] == 2

    summary = client.get("/api/v1/study/summary", headers=student_headers).json()
    assert summary["suggestions"][0]["status"] == "proposed"
    assert "approaching" in summary["suggestions"][0]["explanation"]
    assert summary["suggestions"][0]["conceptId"] == "concept-cell"

    assert client.post(
        f"/api/v1/study/recommendations/{payload['id']}/respond",
        headers=auth_headers(outsider_id),
        json={"decision": "accept"},
    ).status_code == 404
    assert client.post(
        f"/api/v1/study/recommendations/{payload['id']}/respond",
        headers=student_headers,
        json={"decision": "accept"},
    ).json()["status"] == "accepted"
    assert client.get("/api/v1/study/summary", headers=student_headers).json()["suggestions"] == []


def test_new_recommendation_supersedes_the_previous_one(client, db):
    teacher_id = _profile(db, "teacher")
    room = _classroom(db, teacher_id)
    student_id = _profile(db, name="Asha")
    _member(db, room, student_id)
    _snapshot(db, student_id)

    body = {
        "classroomId": str(room.id), "studentId": str(student_id),
        "conceptId": "concept-cell", "actionType": "reinforce_foundations",
        "notes": "Stay with this unit for one more check.",
    }
    first = client.post("/api/v1/teacher/recommendations", headers=auth_headers(teacher_id), json=body).json()
    second = client.post("/api/v1/teacher/recommendations", headers=auth_headers(teacher_id), json=body).json()

    actions = client.get(
        f"/api/v1/teacher/classrooms/{room.id}/evidence-matrix",
        headers=auth_headers(teacher_id),
    ).json()["actions"]
    statuses = {action["id"]: action["status"] for action in actions}
    assert statuses[first["id"]] == "superseded"
    assert statuses[second["id"]] == "proposed"
```

- [ ] **Step 2: Run and confirm failure**

```powershell
.\.venv\Scripts\python -m pytest tests/test_teacher_evidence_scope.py -q
```

Expected: FAIL — `/teacher/evidence` aggregates every student, the matrix has no `concepts`, recommendations use `active` and accept any concept string, and students cannot respond.

Before running the new test, rewrite the existing `backend/tests/test_multi_user_evidence_matrix.py` to the contracts introduced in Tasks 9, 13, 14, and 15:

- Remove the module-level `TestClient(app)` and use the `client`/`db` fixtures.
- Delete the module-level `pytestmark = pytest.mark.skip(...)` that Task 1 added; the rewritten file must run in the normal suite.
- Keep the teacher and three student profiles, but set `subjectScope: "subject-science"`.
- Change every attempt payload to `lessonVersionId` and `questionKey` (no `question_id`, no client `is_correct`, no `concept_id`). Give the seeded question `answer_key_json={"answer": "c", "feedback": "..."}` and let the server grade it.
- Keep the remediation assertion only if `nextAction.remediationInjected` is still part of the Task 9 response; otherwise assert that a `rem_...` lesson appears and drop the response flag.
- Expect the recommendation response status to be `"proposed"`, and assert `reason.evidence.band` instead of the old `"active"` status.
- Use the task 13 dashboard shape; do not reintroduce a 25-minute goal or an invented session count.

- [ ] **Step 3: Scope the evidence queries and remove invented bands**

In `teacher.py`:

- Add `_owned_classroom(db, classroom_id, teacher_id)` returning the classroom or raising `404`.
- In `get_classroom_evidence_matrix`, build `concepts` only from `ConceptMasterySnapshot` rows owned by active members:

```python
snapshots = (
    db.query(ConceptMasterySnapshot)
    .filter(ConceptMasterySnapshot.owner_id == membership.student_id)
    .order_by(ConceptMasterySnapshot.calculated_at.desc())
    .all()
)
concepts = [
    {
        "conceptId": snapshot.concept_id,
        "band": snapshot.estimate_band,
        "score": round((snapshot.numeric_estimate or 0.0) * 100, 1),
        "evidenceCount": snapshot.evidence_count,
        "calculatedAt": snapshot.calculated_at.isoformat() if snapshot.calculated_at else None,
    }
    for snapshot in snapshots
]
rank = {"not_enough_evidence": -1, "developing": 0, "approaching": 1, "demonstrated": 2}
evidence_band = (
    "not_enough_evidence"
    if not concepts
    else min((item["band"] for item in concepts), key=lambda band: rank.get(band, -1))
)
```

- `conceptsDemonstrated = sum(1 for item in concepts if item["band"] == "demonstrated")`; `totalConcepts = len(concepts)`.
- Use `summary["accuracyRate"]` only when it is not `None`; otherwise `0` with `accuracyKnown: False`.
- Remove every branch that infers a band from `accuracyRate`, `checks`, or `improvement`.
- `studentName`: `profile.display_name if profile else "Account removed"`; add `"profileMissing": profile is None`.
- Add `"concepts": concepts`.
- Replace `c.join_code or "SETU-JOIN"` with `c.join_code` and let the UI render “Code unavailable” when null.
- Delete the fuzzy `_normalize_code` fallback in `join_classroom`; query with `func.upper(Classroom.join_code) == code`.
- Replace `/teacher/evidence` with a scoped endpoint:

```python
@router.get("/evidence")
def get_teacher_evidence(
    classroom_id: uuid.UUID = Query(..., alias="classroomId"),
    teacher_id: uuid.UUID = Depends(get_current_teacher_id),
    db: Session = Depends(get_db),
):
    classroom = _owned_classroom(db, classroom_id, teacher_id)
    member_ids = [
        row[0] for row in db.query(ClassroomMembership.student_id).filter(
            ClassroomMembership.classroom_id == classroom.id,
            ClassroomMembership.status == "active",
        ).all()
    ]
    if not member_ids:
        return []
    evidences = db.query(ConceptEvidence).filter(ConceptEvidence.owner_id.in_(member_ids)).all()
    # Aggregate by conceptId. Return one row per concept:
    # {conceptId, totalAttempts, correctAttempts, incorrectAttempts, lastAssessedAt}
    # lastAssessedAt = max(evidence.occurred_at) for that concept.
```

The response is a list ordered by `conceptId`. Do not return evidence rows for members of any other classroom.

- [ ] **Step 4: Store evidence with every recommendation**

In `teacher.py`:

```python
class RecommendationCreate(BaseModel):
    classroomId: uuid.UUID
    studentId: uuid.UUID
    conceptId: str = Field(min_length=1, max_length=100)
    actionType: Literal["reinforce_foundations", "advance_challenge", "targeted_review"]
    notes: str = Field(min_length=3, max_length=1000)
```

In `create_recommendation`:

1. Verify the classroom belongs to the teacher and the student is an active member.
2. Resolve the latest snapshot for that student and concept; if none, raise `422` “No evidence exists for that topic in this classroom yet.”
3. Mark previous `proposed` actions for the same student, classroom, and concept as `superseded` with `resolved_at=utcnow()`.
4. Insert the action with all ownership fields, not only `status`:

```python
action = TeacherAction(
    teacher_id=teacher_id,
    classroom_id=classroom.id,
    student_id=req.studentId,
    action_type=req.actionType,
    status="proposed",
    reason_json={
        "source": "teacher",
        "conceptId": req.conceptId,
        "notes": req.notes.strip(),
        "evidence": {
            "band": snapshot.estimate_band,
            "score": round((snapshot.numeric_estimate or 0.0) * 100, 1),
            "evidenceCount": snapshot.evidence_count,
            "calculatedAt": snapshot.calculated_at.isoformat() if snapshot.calculated_at else None,
        },
    },
)
db.add(action)
db.commit()
db.refresh(action)
```

5. Return `id`, `status`, `actionType`, `conceptId`, `notes`, and `reason` (the full dict).

- [ ] **Step 5: Let only the addressed student respond**

In `study.py` add:

```python
class RecommendationDecision(BaseModel):
    decision: Literal["accept", "dismiss"]
    note: Optional[str] = Field(default=None, max_length=500)


@router.post("/recommendations/{action_id}/respond")
def respond_to_recommendation(
    action_id: uuid.UUID,
    req: RecommendationDecision,
    owner_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    action = db.query(TeacherAction).filter(
        TeacherAction.id == action_id,
        TeacherAction.student_id == owner_id,
        TeacherAction.status == "proposed",
    ).first()
    if not action:
        raise HTTPException(status_code=404, detail="Recommendation not found.")
    action.status = "accepted" if req.decision == "accept" else "dismissed"
    action.resolved_at = datetime.datetime.utcnow()
    reason = dict(action.reason_json or {})
    reason["studentResponse"] = {
        "decision": req.decision,
        "note": (req.note or "").strip()[:500],
        "respondedAt": action.resolved_at.isoformat(),
    }
    action.reason_json = reason
    db.commit()
    return {"id": str(action.id), "status": action.status}
```

In `summarize_student`, filter `TeacherAction.status == "proposed"` (not `"active"`) and return `explanation`:

```python
evidence = reason.get("evidence") or {}
band = evidence.get("band")
count = evidence.get("evidenceCount")
concept = reason.get("conceptId")
explanation = (
    f"Your teacher noticed {band} evidence for {concept} ({count} checks)."
    if band and concept
    else "Your teacher sent a note for your next study session."
)
```

Include `status`, `conceptId`, `teacherName` (look up `UserProfile` by `action.teacher_id`; fall back to “Your teacher”), and `createdAt`.

- [ ] **Step 6: Update the typed client**

In `api.ts`:

```ts
export type EvidenceBand = 'not_enough_evidence' | 'developing' | 'approaching' | 'demonstrated';

export interface EvidenceConceptRow {
  conceptId: string;
  band: EvidenceBand;
  score: number;
  evidenceCount: number;
  calculatedAt: string | null;
}

export interface EvidenceMatrixRow {
  studentId: string;
  studentName: string;
  profileMissing?: boolean;
  concepts: EvidenceConceptRow[];
  conceptsDemonstrated: number;
  totalConcepts: number;
  accuracyRate: number;
  accuracyKnown?: boolean;
  recentAttemptsCount: number;
  evidenceBand: EvidenceBand;
  lastActive: string;
  minutesStudied?: number;
  readingTitle?: string | null;
  improvement?: string;
  heatmap?: Array<{ date: string; seconds: number }>;
  focus?: string;
}

export interface TeacherActionRow {
  id: string;
  studentId: string;
  conceptId: string;
  actionType: string;
  notes: string;
  status: 'proposed' | 'accepted' | 'dismissed' | 'superseded';
  createdAt: string;
}
```

Update `getEvidenceMatrix` to return `actions: TeacherActionRow[]` and add:

```ts
async respondToRecommendation(actionId: string, decision: 'accept' | 'dismiss'): Promise<{ id: string; status: string }> {
  return request(`/study/recommendations/${actionId}/respond`, {
    method: 'POST',
    body: JSON.stringify({ decision }),
  });
}
```

Update the study-summary type with `suggestions: Array<{ id: string; note: string; actionType: string; conceptId: string; status: string; explanation: string; teacherName: string; createdAt?: string }>`.

- [ ] **Step 7: Make the teacher screen show evidence and explanations**

In `TeacherDashboardPage.tsx`:

- Fix `fetchClassrooms` so it does not depend on `selectedClassroomId`; select the first room only when no room is selected.
- Store `actions` from the evidence-matrix response.
- Replace the band ternary with a shared map that includes `not_enough_evidence` → “Not enough evidence”.
- Expand each row with its `concepts`: concept name, band, score, evidence count, last assessed. If `profileMissing`, show “Account removed” and no recommendation control for that row.
- Clicking a row selects the student. The suggestion form’s topic is a `<select>` of that student’s `concepts`; remove `recConcept.trim() || 'current-unit'`. The submit button is disabled until a student, an evidenced concept, and a note are present.
- Show a preview under the topic:

```tsx
{selectedConcept && (
  <p className={styles.evidenceNote}>
    Based on {selectedConcept.band} evidence · {selectedConcept.evidenceCount} checks
    {selectedConcept.calculatedAt ? ` · last assessed ${new Date(selectedConcept.calculatedAt).toLocaleDateString()}` : ''}
  </p>
)}
```

- Replace the feedback-string prefix check with `{ kind: 'ok' | 'error'; message: string }`.
- Add a “Sent suggestions” table with student, concept, action, status, and date. Status labels: Proposed, Accepted, Dismissed, Superseded.
- Empty classroom copy stays: “No students have joined. Share the code above. Their minutes and checks will show here after they study.”

In `HomePage.tsx` “Study record”, render each proposed suggestion with its `explanation` and two buttons:

```tsx
<button type="button" onClick={() => respondToSuggestion(item.id, 'accept')}>Accept</button>
<button type="button" onClick={() => respondToSuggestion(item.id, 'dismiss')}>Dismiss</button>
```

`respondToSuggestion` calls `api.respondToRecommendation`, then `fetchSummary()`. Show the API error inline; do not remove the item optimistically.

- [ ] **Step 8: Add the teacher E2E test**

```ts
// frontend/e2e/teacher_evidence.spec.ts
import { test, expect } from '@playwright/test';

test('teacher sees scoped evidence and sends an explained recommendation', async ({ page }) => {
  const teacher = {
    id: '66666666-6666-4666-8666-666666666666',
    email: 'teacher@example.com', role: 'teacher', displayName: 'Teacher Rao',
    onboardingCompleted: true, tourCompleted: true,
  };
  const room = {
    id: '77777777-7777-4777-8777-777777777777', name: 'Morning Science',
    grade: 9, boardId: 'board-cbse', subjectScope: 'subject-science',
    joinCode: 'ABC123', memberCount: 1, createdAt: '2026-10-01T00:00:00',
  };
  const row = {
    studentId: '55555555-5555-4555-8555-555555555555', studentName: 'Asha',
    concepts: [{ conceptId: 'concept-cell', band: 'approaching', score: 64, evidenceCount: 2, calculatedAt: '2026-10-27T10:00:00' }],
    conceptsDemonstrated: 0, totalConcepts: 1, accuracyRate: 0.5, accuracyKnown: true,
    recentAttemptsCount: 2, evidenceBand: 'approaching', lastActive: '2026-10-27',
    minutesStudied: 12, readingTitle: 'Cells', improvement: 'steady', heatmap: [], focus: 'Review cells.',
  };
  const sent: any[] = [];

  await page.addInitScript(() => localStorage.setItem('setu_auth_token', 'e2e-token'));
  await page.route('**/api/v1/profile', (route) => route.fulfill({ json: teacher }));
  await page.route('**/api/v1/teacher/classrooms', (route) => route.fulfill({ json: [room] }));
  await page.route(`**/api/v1/teacher/classrooms/${room.id}/evidence-matrix`, (route) => {
    if (route.request().method() === 'POST') return route.continue();
    return route.fulfill({ json: { classroomId: room.id, totalStudents: 1, matrix: [row], actions: [] } });
  });
  await page.route('**/api/v1/teacher/recommendations', async (route) => {
    sent.push(route.request().postDataJSON());
    await route.fulfill({ json: {
      id: '88888888-8888-4888-8888-888888888888', status: 'proposed',
      actionType: 'targeted_review', conceptId: 'concept-cell',
      notes: 'Review the worked example.',
      reason: { evidence: row.concepts[0] },
    } });
  });
  await page.route('**/api/v1/catalogue/boards', (route) => route.fulfill({ json: [] }));
  await page.route('**/api/v1/catalogue/subjects', (route) => route.fulfill({ json: [] }));

  await page.goto('/teacher');
  await expect(page.getByText('Asha')).toBeVisible();
  await expect(page.getByText('Approaching')).toBeVisible();
  await page.getByRole('button', { name: /Asha/ }).click();
  await page.getByLabel('Topic').selectOption('concept-cell');
  await expect(page.getByText(/Based on approaching evidence/)).toBeVisible();
  await page.getByLabel('Note').fill('Review the worked example.');
  await page.getByRole('button', { name: /Send suggestion/ }).click();
  await expect.poll(() => sent.length).toBe(1);
  expect(sent[0].conceptId).toBe('concept-cell');
  expect(sent[0].notes).toBe('Review the worked example.');
});
```

- [ ] **Step 9: Run the tests**

```powershell
cd backend
.\.venv\Scripts\python -m pytest tests/test_teacher_evidence_scope.py tests/test_multi_user_evidence_matrix.py -q
cd ..\frontend
npm run build
npx playwright test e2e/teacher_evidence.spec.ts --project=chromium
```

Expected: PASS. A teacher cannot read another classroom, the matrix only contains active members with real snapshots, recommendations cite the snapshot, and only the addressed student can accept or dismiss one.

- [ ] **Step 10: Commit**

```bash
git add backend/app/api/v1/teacher.py backend/app/api/v1/study.py backend/tests/test_teacher_evidence_scope.py backend/tests/test_multi_user_evidence_matrix.py frontend/src/services/api.ts frontend/src/pages/TeacherDashboardPage.tsx frontend/src/pages/TeacherDashboardPage.module.css frontend/src/pages/HomePage.tsx frontend/e2e/teacher_evidence.spec.ts
git commit -m "feat: scope teacher evidence and make recommendations explainable"
```

### Task 15: Load Boards, Subjects, and Languages from the API

**Files:**
- Modify: `backend/app/api/v1/auth.py`
- Modify: `backend/app/api/v1/profile.py`
- Modify: `backend/app/api/v1/teacher.py`
- Create: `backend/tests/test_taxonomy_validation.py`
- Modify: `frontend/src/services/api.ts`
- Create: `frontend/src/lib/academic.ts`
- Create: `frontend/src/hooks/useTaxonomy.ts`
- Modify: `frontend/src/components/AuthModal.tsx`
- Modify: `frontend/src/components/AuthModal.module.css`
- Modify: `frontend/src/components/OnboardingTour.tsx`
- Modify: `frontend/src/components/OnboardingTour.module.css`
- Modify: `frontend/src/pages/StudentDashboardPage.tsx`
- Modify: `frontend/src/pages/TeacherDashboardPage.tsx`
- Modify: `frontend/src/context/AuthContext.tsx`
- Create: `frontend/e2e/onboarding_taxonomy.spec.ts`

**Interfaces:**
- Consumes: `GET /catalogue/boards`, `GET /catalogue/subjects`, `GET /catalogue/languages`, `CurriculumBoard`, `Subject`, `Language`.
- Produces: `useTaxonomy(enabled)` returning `{ boards, subjects, languages, loading, error, retry }`; `GRADES` as the only shared class list; signup/profile/classroom validation rejects unknown boards, subjects, languages, grades outside 6–10, and missing academic context before onboarding can be completed; `AuthContext.signup` returns the created `UserProfileData`.

- [ ] **Step 1: Write the failing validation tests**

```python
# backend/tests/test_taxonomy_validation.py
import uuid

from app.models.profiles import UserProfile
from tests.conftest import auth_headers


def _student(db):
    user_id = uuid.uuid4()
    db.add(UserProfile(
        id=user_id, email="student@example.com", display_name="Asha", role="student",
    ))
    db.commit()
    return user_id


def test_profile_rejects_an_unknown_board(client, db):
    student_id = _student(db)
    response = client.put(
        "/api/v1/profile", headers=auth_headers(student_id),
        json={"boardId": "board-not-real"},
    )
    assert response.status_code == 422
    assert "board" in response.json()["detail"].lower()


def test_profile_rejects_an_unknown_language(client, db):
    student_id = _student(db)
    response = client.put(
        "/api/v1/profile", headers=auth_headers(student_id),
        json={"preferredLanguage": "xx-XX"},
    )
    assert response.status_code == 422
    assert "language" in response.json()["detail"].lower()


def test_profile_rejects_an_unknown_subject(client, db):
    student_id = _student(db)
    response = client.put(
        "/api/v1/profile", headers=auth_headers(student_id),
        json={"subjectsInterested": ["subject-astrology"]},
    )
    assert response.status_code == 422
    assert "subject" in response.json()["detail"].lower()


def test_profile_rejects_a_grade_outside_classes_6_to_10(client, db):
    student_id = _student(db)
    assert client.put(
        "/api/v1/profile", headers=auth_headers(student_id), json={"grade": 11},
    ).status_code == 422
    assert client.put(
        "/api/v1/profile", headers=auth_headers(student_id), json={"dailyGoalMinutes": 5},
    ).status_code == 422


def test_profile_cannot_escalate_its_own_role(client, db):
    student_id = _student(db)
    response = client.put(
        "/api/v1/profile", headers=auth_headers(student_id), json={"role": "teacher"},
    )
    assert response.status_code == 200
    assert response.json()["profile"]["role"] == "student"
    assert db.get(UserProfile, student_id).role == "student"


def test_onboarding_cannot_finish_without_academic_context(client, db):
    student_id = _student(db)
    response = client.put(
        "/api/v1/profile", headers=auth_headers(student_id),
        json={"onboardingCompleted": True},
    )
    assert response.status_code == 422
    assert "class" in response.json()["detail"].lower()


def test_valid_academic_context_is_persisted(client, db):
    student_id = _student(db)
    response = client.put(
        "/api/v1/profile", headers=auth_headers(student_id),
        json={
            "grade": 9, "boardId": "board-cbse", "preferredLanguage": "en-IN",
            "subjectsInterested": ["subject-science"], "dailyGoalMinutes": 30,
            "onboardingCompleted": True,
        },
    )
    assert response.status_code == 200
    profile = response.json()["profile"]
    assert profile["grade"] == 9
    assert profile["boardId"] == "board-cbse"
    assert profile["preferredLanguage"] == "en-IN"
    assert profile["onboardingCompleted"] is True


def test_signup_validates_before_calling_supabase(client, monkeypatch):
    called = {"value": False}

    class _ForbiddenClient:
        def __init__(self, *args, **kwargs):
            called["value"] = True
            raise AssertionError("Supabase must not be called for invalid taxonomy")

    monkeypatch.setattr("app.api.v1.auth.httpx.AsyncClient", _ForbiddenClient)
    response = client.post("/api/v1/auth/signup", json={
        "email": "new@example.com", "password": "secret123", "displayName": "New Learner",
        "role": "student", "grade": 9, "boardId": "board-not-real",
    })
    assert response.status_code == 422
    assert called["value"] is False
```

- [ ] **Step 2: Run and confirm failure**

```powershell
.\.venv\Scripts\python -m pytest tests/test_taxonomy_validation.py -q
```

Expected: FAIL — unknown IDs are accepted, onboarding can finish with no academic context, and signup reaches the auth provider before validating the board.

- [ ] **Step 3: Validate academic context on the server**

In `profile.py`, replace `ProfileUpdateRequest` with:

```python
class ProfileUpdateRequest(BaseModel):
    displayName: Optional[str] = Field(default=None, min_length=1, max_length=150)
    grade: Optional[int] = Field(default=None, ge=6, le=10)
    boardId: Optional[str] = None
    preferredLanguage: Optional[str] = None
    subjectsInterested: Optional[List[str]] = None
    learningGoals: Optional[List[str]] = None
    dailyGoalMinutes: Optional[int] = Field(default=None, ge=10, le=120)
    accessibilityPreferences: Optional[Dict[str, Any]] = None
    onboardingCompleted: Optional[bool] = None
    tourCompleted: Optional[bool] = None
```

Remove `role` completely. In `update_profile`, validate before assigning:

```python
if req.boardId is not None:
    board = db.query(CurriculumBoard).filter(
        CurriculumBoard.id == req.boardId, CurriculumBoard.active.is_(True)
    ).first()
    if not board:
        raise HTTPException(status_code=422, detail="Choose a curriculum board from the list.")

if req.preferredLanguage is not None:
    language = db.query(Language).filter(
        Language.bcp47_tag == req.preferredLanguage, Language.active.is_(True)
    ).first()
    if not language:
        raise HTTPException(status_code=422, detail="Choose a language from the list.")

if req.subjectsInterested is not None:
    requested = list(dict.fromkeys(req.subjectsInterested))
    valid = {
        subject.id for subject in db.query(Subject).filter(
            Subject.id.in_(requested), Subject.active.is_(True)
        ).all()
    }
    if len(valid) != len(requested):
        raise HTTPException(status_code=422, detail="One or more subjects are not available.")

prospective_grade = req.grade if req.grade is not None else profile.grade
prospective_board = req.boardId if req.boardId is not None else profile.board_id
prospective_language = (
    req.preferredLanguage if req.preferredLanguage is not None else profile.preferred_language
)
if req.onboardingCompleted and profile.role == "student":
    if not (prospective_grade and prospective_board and prospective_language):
        raise HTTPException(
            status_code=422,
            detail="Choose your class, board, and language before finishing setup.",
        )
```

Apply the same board/language validation in `auth.py` `signup` before the `httpx.AsyncClient` block:

```python
if req.grade is not None and not 6 <= req.grade <= 10:
    raise HTTPException(status_code=422, detail="Class must be between 6 and 10.")
if req.boardId:
    if not db.query(CurriculumBoard).filter(
        CurriculumBoard.id == req.boardId, CurriculumBoard.active.is_(True)
    ).first():
        raise HTTPException(status_code=422, detail="Choose a curriculum board from the list.")
if req.preferredLanguage:
    if not db.query(Language).filter(
        Language.bcp47_tag == req.preferredLanguage, Language.active.is_(True)
    ).first():
        raise HTTPException(status_code=422, detail="Choose a language from the list.")
```

Imports: `Field` from `pydantic`; `CurriculumBoard`, `Subject`, `Language` from `app.models.curriculum`.

In `teacher.py`, validate classroom context:

```python
class ClassroomCreate(BaseModel):
    name: str = Field(min_length=2, max_length=150)
    grade: int = Field(ge=6, le=10)
    boardId: str
    subjectScope: str
```

Before creating the classroom, reject a missing active board or subject with `422`. Do not default the grade, board, or subject.

- [ ] **Step 4: Add the shared taxonomy client and hook**

In `api.ts` add:

```ts
export interface CatalogueSubject {
  id: string;
  code: string;
  canonicalName: string;
  name: string;
}

export interface CatalogueLanguage {
  id: string;
  bcp47Tag: string;
  nativeName: string;
  script: string;
}

async getSubjects(): Promise<CatalogueSubject[]> {
  return request<CatalogueSubject[]>('/catalogue/subjects');
},

async getLanguages(): Promise<CatalogueLanguage[]> {
  return request<CatalogueLanguage[]>('/catalogue/languages');
},
```

Create `frontend/src/lib/academic.ts`:

```ts
export const GRADES = [6, 7, 8, 9, 10] as const;
export type Grade = (typeof GRADES)[number];
export const gradeLabel = (grade: number) => `Class ${grade}`;
```

Create `frontend/src/hooks/useTaxonomy.ts`:

```ts
import { useCallback, useEffect, useState } from 'react';
import {
  api,
  CatalogueBoard,
  CatalogueLanguage,
  CatalogueSubject,
} from '../services/api';

export function useTaxonomy(enabled = true) {
  const [boards, setBoards] = useState<CatalogueBoard[]>([]);
  const [subjects, setSubjects] = useState<CatalogueSubject[]>([]);
  const [languages, setLanguages] = useState<CatalogueLanguage[]>([]);
  const [loading, setLoading] = useState(enabled);
  const [error, setError] = useState<string | null>(null);
  const [reloadToken, setReloadToken] = useState(0);

  useEffect(() => {
    if (!enabled) return;
    let cancelled = false;
    setLoading(true);
    setError(null);
    Promise.all([api.getBoards(), api.getSubjects(), api.getLanguages()])
      .then(([boardRows, subjectRows, languageRows]) => {
        if (cancelled) return;
        setBoards(boardRows);
        setSubjects(subjectRows);
        setLanguages(languageRows);
      })
      .catch(() => {
        if (!cancelled) setError('Could not load boards, subjects, and languages.');
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => { cancelled = true; };
  }, [enabled, reloadToken]);

  const retry = useCallback(() => setReloadToken((value) => value + 1), []);
  return { boards, subjects, languages, loading, error, retry };
}
```

- [ ] **Step 5: Remove every hardcoded board/subject/language list**

In `AuthModal.tsx`:

- Import `useTaxonomy`, `GRADES`, `gradeLabel`.
- State: `const [grade, setGrade] = useState<number | ''>('');`, `const [boardId, setBoardId] = useState('');`, `const [preferredLanguage, setPreferredLanguage] = useState('');`.
- `const taxonomy = useTaxonomy(isOpen && tab === 'signup' && role === 'student');`.
- Student selects render `GRADES.map((value) => <option key={value} value={value}>{gradeLabel(value)}</option>)`, `taxonomy.boards`, and `taxonomy.languages`, each with an empty placeholder option (`Select class`, `Select a board`, `Select a language`) and `required`.
- Show `taxonomy.error` with a Retry button; show a loading line while `taxonomy.loading`.
- Submit student signup only when `grade !== ''`, `boardId`, and `preferredLanguage` are present. Pass them as real values; teacher signup omits them.
- If a student list is empty after loading, show “No boards are available. Ask an administrator to add reference data.” and disable signup. Never substitute a local option.

In `OnboardingTour.tsx`:

- Import `useTaxonomy`, `GRADES`, `gradeLabel`, and `UserProfileData`. Use `useEffect` and `useRef` from React.
- Initialize `grade` as `number | ''`, `boardId`, `preferredLanguage`, `selectedSubjects` as `[]`, `pace` as `''`, `dailyMinutes` as `number | ''`, `learningGoals` as `[]`. Remove every `|| 9`, `|| 'board-cbse'`, `|| 'en-IN'`, `|| ['subject-science', ...]`, `|| ['Concept Mastery', ...]`, and `|| 30`.
- On open, reset to the signed-in profile’s real values (`?? ''` / `?? []`); do not reset a second time after the user edits. Use an open-transition guard, not an effect keyed only on `user`:

```tsx
const wasOpen = useRef(false);

useEffect(() => {
  if (!isOpen) {
    wasOpen.current = false;
    return;
  }
  if (wasOpen.current) return;
  wasOpen.current = true;
  setGrade(user?.grade ?? '');
  setBoardId(user?.boardId ?? '');
  setPreferredLanguage(user?.preferredLanguage ?? '');
  setSelectedSubjects(user?.subjectsInterested ?? []);
  setPace((user?.accessibilityPreferences?.pace as 'short' | 'steady' | 'long') ?? '');
  setDailyMinutes(user?.dailyGoalMinutes ?? '');
  setLearningGoals(user?.learningGoals ?? []);
}, [isOpen, user]);
```

Do not include `step` in this effect. The signup flow advances the step explicitly; resetting it on a `user` change would send a new account back to the welcome screen.
- Render boards, subjects, and languages from `useTaxonomy(isOpen)`; show its error and Retry.
- Registration step: require class, board, and language for students; send only the chosen values.
- Academic step for an existing student: same fields, no defaults.
- Step 3: no selected pace or daily minutes by default. The user may skip either.
- `handleFinishPreferences` validates for students:

```ts
if (user?.role !== 'teacher' && (grade === '' || !boardId || !preferredLanguage)) {
  setPreferencesError('Choose your class, board, and language before finishing setup.');
  return;
}
```

Build the update from chosen values only:

```ts
const updates: Partial<UserProfileData> = {
  onboardingCompleted: true,
  tourCompleted: true,
  learningGoals,
};
if (user?.role !== 'teacher') {
  updates.grade = Number(grade);
  updates.boardId = boardId;
  updates.preferredLanguage = preferredLanguage;
  updates.subjectsInterested = selectedSubjects;
}
if (pace) {
  updates.accessibilityPreferences = { ...(user?.accessibilityPreferences || {}), pace };
}
if (dailyMinutes !== '') updates.dailyGoalMinutes = Number(dailyMinutes);
await updateProfile(updates);
```

- If the signed-in user is a teacher, skip the academic fields and the habits step; the step-2 action finishes onboarding with only the completion flags.
- `AuthContext.signup` returns `Promise<UserProfileData>` and returns `res.user`. In `OnboardingTour`, capture the created profile; if it is a teacher, call `updateProfile({ onboardingCompleted: true, tourCompleted: true })` and close; if a student, advance to step 3.

In `StudentDashboardPage.tsx`, replace the single boards fetch with `useTaxonomy(isEditOpen)` and add a language select. Save only non-empty values. Remove the last hardcoded board option.

In `TeacherDashboardPage.tsx`, replace the grade/board/subject option arrays with `GRADES`, `useTaxonomy(true)`, and empty placeholders. Keep `New classroom` disabled until a name, class, board, and subject are chosen.

- [ ] **Step 6: Write the onboarding E2E test**

```ts
// frontend/e2e/onboarding_taxonomy.spec.ts
import { test, expect } from '@playwright/test';

test('onboarding loads reference data and starts with no academic selection', async ({ page }) => {
  await page.route('**/api/v1/catalogue/boards', (route) => route.fulfill({
    json: [{ id: 'board-test', code: 'TEST', name: 'Test Board Alpha' }],
  }));
  await page.route('**/api/v1/catalogue/subjects', (route) => route.fulfill({
    json: [{ id: 'subject-test', code: 'TEST', canonicalName: 'Test Subject', name: 'Test Subject' }],
  }));
  await page.route('**/api/v1/catalogue/languages', (route) => route.fulfill({
    json: [{ id: 'lang-test', bcp47Tag: 'en-TEST', nativeName: 'Test Language', script: 'Latn' }],
  }));

  await page.goto('/');
  await page.getByRole('button', { name: /Get Started/ }).click();
  const dialog = page.getByRole('dialog');
  await dialog.getByRole('button', { name: 'Continue' }).click();
  await dialog.getByRole('button', { name: 'Continue to Registration →' }).click();

  await expect(dialog.locator('select#tour-reg-grade')).toHaveValue('');
  await expect(dialog.locator('select#tour-reg-board')).toHaveValue('');
  await expect(dialog.locator('select#tour-reg-lang')).toHaveValue('');
  await expect(dialog.locator('select#tour-reg-board option')).toHaveText([
    'Select a board',
    'Test Board Alpha',
  ]);
  await expect(dialog.locator('select#tour-reg-board option', { hasText: 'CBSE' })).toHaveCount(0);
});
```

- [ ] **Step 7: Run the tests**

```powershell
cd backend
.\.venv\Scripts\python -m pytest tests/test_taxonomy_validation.py -q
cd ..\frontend
npm run build
npx playwright test e2e/onboarding_taxonomy.spec.ts --project=chromium
```

Expected: PASS. Unknown IDs are rejected before any account is created, onboarding starts empty, and every option comes from the catalogue API.

- [ ] **Step 8: Commit**

```bash
git add backend/app/api/v1/auth.py backend/app/api/v1/profile.py backend/app/api/v1/teacher.py backend/tests/test_taxonomy_validation.py frontend/src/services/api.ts frontend/src/lib/academic.ts frontend/src/hooks/useTaxonomy.ts frontend/src/components/AuthModal.tsx frontend/src/components/AuthModal.module.css frontend/src/components/OnboardingTour.tsx frontend/src/components/OnboardingTour.module.css frontend/src/pages/StudentDashboardPage.tsx frontend/src/pages/TeacherDashboardPage.tsx frontend/src/context/AuthContext.tsx frontend/e2e/onboarding_taxonomy.spec.ts
git commit -m "feat: load academic taxonomy from the API and validate it"
```

---

### Task 16: Make Every Route, Button, Visual, and Claim Honest

**Files:**
- Create: `frontend/src/components/AuthGate.tsx`
- Create: `frontend/src/pages/NotFoundPage.tsx`
- Create: `frontend/src/pages/NotFoundPage.module.css`
- Create: `frontend/src/components/visuals/ProcessDiagram.tsx`
- Create: `frontend/src/components/visuals/ProcessDiagram.module.css`
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/components/Navigation.tsx`
- Modify: `frontend/src/pages/HomePage.tsx`
- Modify: `frontend/src/pages/HomePage.module.css`
- Modify: `frontend/src/pages/LessonReaderPage.tsx`
- Modify: `frontend/src/pages/DoubtQueuePage.tsx`
- Modify: `frontend/src/components/visuals/VisualRenderer.tsx`
- Modify: `frontend/src/components/OnboardingTour.tsx`
- Modify: `frontend/vite.config.ts`
- Modify: `backend/app/main.py`
- Delete: `frontend/e2e/setu_full_e2e.spec.ts`
- Create: `frontend/e2e/navigation_truth.spec.ts`
- Create: `docs/UI_ACTION_AUDIT.md`

**Interfaces:**
- Consumes: `useAuth`, `AuthModal`, `VisualRenderer`, `api.getLesson`, `saveLessonOffline`.
- Produces: `AuthGate` for protected routes; a not-found route; a guest navigation that exposes only real actions; a `ProcessDiagram` that never renders cell-membrane art for unrelated processes; download feedback; a complete action audit.

- [ ] **Step 1: Add route guards and a not-found page**

Create `AuthGate.tsx`:

```tsx
import React, { ReactNode, useState } from 'react';
import { useAuth } from '../context/AuthContext';
import { AuthModal } from './AuthModal';

export const AuthGate: React.FC<{ children: ReactNode; teacherOnly?: boolean }> = ({
  children,
  teacherOnly = false,
}) => {
  const { user, isLoading } = useAuth();
  const [isAuthOpen, setIsAuthOpen] = useState(false);

  if (isLoading) return <p style={{ padding: 32 }}>Loading SETU…</p>;

  if (!user) {
    return (
      <section style={{ maxWidth: 720, margin: '48px auto', padding: '0 24px' }}>
        <h1 style={{ fontSize: 28, marginBottom: 8 }}>Your learning desk</h1>
        <p>Sign in to open your lessons, progress, and doubts.</p>
        <button type="button" onClick={() => setIsAuthOpen(true)}>Sign in or create an account</button>
        <AuthModal isOpen={isAuthOpen} onClose={() => setIsAuthOpen(false)} />
      </section>
    );
  }

  if (teacherOnly && user.role !== 'teacher') {
    return (
      <section style={{ maxWidth: 720, margin: '48px auto', padding: '0 24px' }}>
        <h1 style={{ fontSize: 28, marginBottom: 8 }}>Teacher account required</h1>
        <p>This page shows classroom evidence. Sign in with a teacher account to continue.</p>
      </section>
    );
  }

  return <>{children}</>;
};
```

In `App.tsx`, remove `TeacherOnly` and wrap routes:

```tsx
<Route path="/" element={<StudentOnly><HomePage /></StudentOnly>} />
<Route path="/dashboard" element={<AuthGate><StudentOnly><StudentDashboardPage /></StudentOnly></AuthGate>} />
<Route path="/lesson/:lessonId" element={<AuthGate><StudentOnly><LessonReaderPage /></StudentOnly></AuthGate>} />
<Route path="/library" element={<AuthGate><StudentOnly><OfflineLibraryPage /></StudentOnly></AuthGate>} />
<Route path="/doubts" element={<AuthGate><StudentOnly><DoubtQueuePage /></StudentOnly></AuthGate>} />
<Route path="/teacher" element={<AuthGate teacherOnly><TeacherDashboardPage /></AuthGate>} />
<Route path="*" element={<NotFoundPage />} />
```

`StudentOnly` must wait for `isLoading` too; return `null` while loading, then redirect teachers to `/teacher`.

- [ ] **Step 2: Make guest navigation honest**

In `Navigation.tsx`:

```tsx
{!user ? (
  <NavLink to="/" end className={linkClass}>Home</NavLink>
) : user.role === 'teacher' ? (
  <NavLink to="/teacher" className={linkClass}>Classroom</NavLink>
) : (
  <>
    <NavLink to="/" end className={linkClass}>Home</NavLink>
    <NavLink to="/dashboard" className={linkClass}>Dashboard</NavLink>
    {lessonHref !== '/' && <NavLink to={lessonHref} className={linkClass}>Lesson</NavLink>}
    <NavLink to="/doubts" className={linkClass}>
      Doubts{pendingCount > 0 ? ` (${pendingCount})` : ''}
    </NavLink>
    <NavLink to="/library" className={linkClass}>Downloads</NavLink>
  </>
)}
```

- Rename the sync button to “Sync now” because it syncs attempts and doubts.
- Rename “Get Started” to `user ? 'How SETU works' : 'Get started'`.
- Add `title={isOnline ? 'Connected' : 'Offline. Work is saved on this device and syncs when you reconnect.'}` to the status badge.
- Ensure `lessonHref` resets to `/` when `user` is null and whenever the path request fails.

- [ ] **Step 3: Fix the process visual and remove the fake fallback**

Create `ProcessDiagram.tsx`:

```tsx
import React from 'react';
import styles from './ProcessDiagram.module.css';

interface ProcessDiagramProps {
  title?: string;
  steps: Array<string | { label?: string; detail?: string }>;
  altText?: string;
}

export const ProcessDiagram: React.FC<ProcessDiagramProps> = ({ title, steps, altText }) => {
  const normalized = steps
    .map((step) => typeof step === 'string'
      ? { label: step }
      : { label: String(step.label || ''), detail: step.detail ? String(step.detail) : undefined })
    .filter((step) => step.label);

  if (normalized.length === 0) return null;

  return (
    <figure className={styles.figure} role="img" aria-label={altText || title || 'Process diagram'}>
      {title && <figcaption className={styles.title}>{title}</figcaption>}
      <ol className={styles.steps}>
        {normalized.map((step, index) => (
          <li key={`${step.label}-${index}`} className={styles.step}>
            <span className={styles.number}>{index + 1}</span>
            <span>
              <strong>{step.label}</strong>
              {step.detail && <span className={styles.detail}>{step.detail}</span>}
            </span>
          </li>
        ))}
      </ol>
    </figure>
  );
};
```

In `VisualRenderer.tsx`:

```tsx
case 'cell_membrane':
  return <CellMembrane altText={altText} labels={data.labels} />;
case 'science_process': {
  const steps = Array.isArray(data.steps) ? data.steps : [];
  return steps.length > 0
    ? <ProcessDiagram title={data.title} steps={steps} altText={altText} />
    : <p>This process visual is not available for this lesson.</p>;
}
default:
  return <p>{altText || 'This visual is not available for this lesson.'}</p>;
```

Delete the “Pedagogical Concept Visual” and `Type: {type}` fallback. Never route an unknown `science_process` to `CellMembrane`.

- [ ] **Step 4: Make download actions report success and failure**

In `HomePage.tsx`:

```tsx
const [downloadingLessonId, setDownloadingLessonId] = useState<string | null>(null);
const [downloadNotice, setDownloadNotice] = useState<{ kind: 'ok' | 'error'; message: string } | null>(null);

const downloadLesson = async (lessonId: string) => {
  setDownloadingLessonId(lessonId);
  setDownloadNotice(null);
  try {
    const pkg = await api.getLesson(lessonId);
    await saveLessonOffline(pkg);
    setDownloadNotice({ kind: 'ok', message: 'Saved for offline reading.' });
  } catch {
    setDownloadNotice({ kind: 'error', message: 'Could not save this lesson. Try again when you are online.' });
  } finally {
    setDownloadingLessonId(null);
  }
};
```

Render the notice in the Continue panel and disable the Download button while that lesson is saving. Change the label to `Saving…` during the request.

Replace the clickable `<li>` unit rows with real buttons:

```tsx
<li key={lesson.id} className={lesson.status === 'ready' ? styles.unitReady : styles.unitWait}>
  <button
    type="button"
    className={styles.unitButton}
    disabled={lesson.status !== 'ready'}
    onClick={() => navigate(`/lesson/${lesson.id}?pathId=${plan.id}`)}
  >
    <span>{lesson.sequence}. {lesson.title}</span>
    <small>{/* existing status copy */}</small>
  </button>
</li>
```

Add `.unitButton` styles that preserve the existing rail appearance and `cursor: not-allowed` for disabled units. A unit that is not ready must be disabled, not silently non-clickable.

- [ ] **Step 5: Replace overclaims in student and onboarding copy**

In `HomePage.tsx` and `OnboardingTour.tsx`:

- Replace “verified textbooks” and “No hallucinated facts” with “the sources you add”.
- Replace “Every explanation … is derived from real NCERT/CBSE textbooks” with “Every explanation and citation is checked against the document you upload.”
- Say “If the source does not contain enough evidence, SETU says so instead of inventing an answer.”
- Keep “Classes 6–10”, “Learn · Solve · Test”, and “Download lessons … queue doubts offline” only where those features are implemented.
- Remove “No hallucinated facts”, “100%”, “verified”, “zero hallucinations”, and “every” where the implementation does not guarantee it.
- Replace “Verified Textbook Citation” with “Source citation”, “Verified Answer” with “Answer from your sources”, and “Extracted from original verified syllabus document” with “Extracted from the document you uploaded.”

In `DoubtQueuePage.tsx`, replace “VERIFIED TEXTBOOK ANSWER” with “ANSWER FROM YOUR SOURCES” and “Verified in source” with “Source pages”.

In `LessonReaderPage.tsx`, remove any remaining fixed-time claims and “Your evidence snapshot has been updated” copy. Show the server’s `feedback` and `nextAction.reason` instead.

- [ ] **Step 6: Set product metadata without a version suffix**

In `backend/app/main.py`, change `version="2.0.0"` to `version="1.0.0"`.

In `frontend/vite.config.ts`, change the manifest description to:

```ts
description: 'Source-grounded adaptive learning desk for Classes 6-10',
```

- [ ] **Step 7: Replace the stale Playwright spec with current navigation tests**

Delete `frontend/e2e/setu_full_e2e.spec.ts`; it asserts screens that no longer exist (“Academic Context”, “Touring the SETU Desk”) and would always fail.

Create `navigation_truth.spec.ts`:

```ts
import { test, expect } from '@playwright/test';

test('an unknown route renders a real not-found page', async ({ page }) => {
  await page.goto('/this-route-does-not-exist');
  await expect(page.getByRole('heading', { name: 'Page not found' })).toBeVisible();
  await expect(page.getByRole('link', { name: 'Back to SETU' })).toHaveAttribute('href', '/');
});

test('a guest sees only real navigation and protected routes ask for sign-in', async ({ page }) => {
  await page.goto('/');
  await expect(page.getByRole('link', { name: 'Dashboard' })).toHaveCount(0);
  await expect(page.getByRole('link', { name: 'Downloads' })).toHaveCount(0);

  await page.goto('/dashboard');
  await expect(page.getByText('Sign in to open your lessons, progress, and doubts.')).toBeVisible();
  await page.getByRole('button', { name: 'Sign in or create an account' }).click();
  await expect(page.getByRole('dialog')).toBeVisible();
});
```

Create `NotFoundPage.tsx` with an `<h1>Page not found</h1>`, a sentence that the route does not exist, and a `<Link to="/">Back to SETU</Link>`. Style it with `NotFoundPage.module.css`.

- [ ] **Step 8: Create the action audit**

Create `docs/UI_ACTION_AUDIT.md` with this header and one row per visible control:

```markdown
# SETU UI Action Audit

Date:
Build:

| Screen | Control | Handler / destination | Requires sign-in | Loading state | Disabled reason | Verified by |
|---|---|---|---|---|---|---|
| Global | Home | `/` | No | — | — | manual |
| Global | Dashboard | `/dashboard` guarded by AuthGate | Yes | Loading SETU… | — | e2e |
| Global | Lesson | first ready lesson | Yes | — | Hidden until a ready lesson exists | manual |
| Global | Doubts | `/doubts` guarded by AuthGate | Yes | — | — | e2e |
| Global | Downloads | `/library` guarded by AuthGate | Yes | — | — | e2e |
| Global | Sync now | `syncManager.syncPendingData()` | Yes | Syncing | Hidden when no pending work | manual |
| Global | How SETU works / Get started | opens onboarding | No | — | — | e2e |
| Global | Sign in / Sign out | AuthModal / clear session | No / Yes | Processing… | — | e2e |
| Auth | Sign In / Register tabs | switch mode | No | — | — | manual |
| Auth | Create account | `signup` | No | Processing… | Missing class, board, language, or taxonomy failure | manual |
| Onboarding | Continue / Back / Skip | step changes | No | — | — | e2e |
| Onboarding | Enter SETU Desk | `updateProfile` | Yes | Saving… | Missing class, board, or language for students | manual |
| Home | Classroom code Join | `POST /teacher/join` | Yes | Joining… | Empty code | manual |
| Home | Book chip | selects current book | Yes | — | — | manual |
| Home | Retry | `retryDocument` | Yes | polling | Only for failed/needs_ocr | manual |
| Home | Build my learning plan | `createLearningPath` | Yes | Building… | Not ready or path already exists | manual |
| Home | Unit row | navigates to ready lesson | Yes | — | Disabled unless status is ready | manual |
| Home | Read | navigates to ready lesson | Yes | — | — | manual |
| Home | Download | `saveLessonOffline` | Yes | Saving… | Already downloading | manual |
| Home | Upload / Cancel | upload XHR / abort | Yes | Uploading… | File over 50MB | manual |
| Lesson | Learn / Solve / Test | tab switch | Yes | — | — | manual |
| Lesson | Save Offline | `saveLessonOffline` | Yes | Saving | IndexedDB failure shows an error | manual |
| Lesson | Ask Doubt / Send | online doubt or offline queue | Yes | Sending… | Empty question | e2e |
| Lesson | Check Answer | `POST /attempts` | Yes | Checking… | Empty response | e2e |
| Dashboard | Edit academic details | opens modal | Yes | — | — | manual |
| Dashboard | Save changes | `PUT /profile` | Yes | Saving… | Missing class/board or taxonomy failure | manual |
| Dashboard | Join Classroom | `POST /teacher/join` | Yes | Joining… | Empty code | manual |
| Teacher | New classroom | toggles form | Yes | — | — | manual |
| Teacher | Create classroom | `POST /teacher/classrooms` | Teacher | Creating… | Missing name/class/board/subject | manual |
| Teacher | Copy code | clipboard | Teacher | — | No code available | manual |
| Teacher | Send suggestion | `POST /teacher/recommendations` | Teacher | Sending… | No student, concept, or note | e2e |
| Doubts | Sync now | `syncPendingData` | Yes | Syncing | — | e2e |
| Doubts | Retry | `POST /doubts` with same client ID | Yes | Retrying… | Only for retryable/rejected | manual |
| Library | Open Offline | lesson route | Yes | — | — | manual |
| Library | Delete | `deleteOfflineLesson` | Yes | — | — | manual |
| Not found | Back to SETU | `/` | No | — | — | e2e |
```

Every row must end with a real verification method (`e2e`, `pytest`, or `manual check on <date>`). A row with no handler or no disabled reason is a defect; fix it before marking the task complete.

- [ ] **Step 9: Run the tests**

```powershell
cd frontend
npm run build
npx playwright test e2e/navigation_truth.spec.ts --project=chromium
```

Expected: PASS. Unknown routes render a not-found page, guests cannot open protected pages, and the stale spec is gone.

- [ ] **Step 10: Commit**

```bash
git add frontend/src/components/AuthGate.tsx frontend/src/pages/NotFoundPage.tsx frontend/src/pages/NotFoundPage.module.css frontend/src/components/visuals/ProcessDiagram.tsx frontend/src/components/visuals/ProcessDiagram.module.css frontend/src/App.tsx frontend/src/components/Navigation.tsx frontend/src/pages/HomePage.tsx frontend/src/pages/HomePage.module.css frontend/src/pages/LessonReaderPage.tsx frontend/src/pages/DoubtQueuePage.tsx frontend/src/components/visuals/VisualRenderer.tsx frontend/src/components/OnboardingTour.tsx frontend/vite.config.ts backend/app/main.py frontend/e2e/navigation_truth.spec.ts docs/UI_ACTION_AUDIT.md
git rm frontend/e2e/setu_full_e2e.spec.ts
git commit -m "fix: guard routes and make navigation, visuals, and copy truthful"
```

---

### Task 17: Prove the Clean State, Guard Destructive Ops, and Report Honestly

**Files:**
- Modify: `backend/scripts/reset_supabase_app_data.py`
- Create: `backend/tests/test_reset_guard.py`
- Create: `backend/tests/test_fresh_account_clean_state.py`
- Create: `docs/OPERATIONS.md`
- Modify: `context/ACCEPTANCE_MATRIX.md`
- Modify: `STATUS_REPORT.md`
- Modify: `context/SUPABASE_CLEANUP_MANIFEST.md` (record the final inventory)
- Optionally modify: `README.md` only if it contains false claims

**Interfaces:**
- Consumes: all previous tasks; the disposable test database; `cleanup_demo_data.py --inventory`.
- Produces: `require_reset_confirmation(args)` with an exact confirmation string, a non-empty backup file, and a production acknowledgement; a fresh-account acceptance test; truthful operations, acceptance, and status documents.

- [ ] **Step 1: Guard the destructive reset script**

Rewrite `backend/scripts/reset_supabase_app_data.py` so importing it has no side effects and `main()` owns all database work. Add:

```python
import argparse
from pathlib import Path

CONFIRMATION = "DROP-ALL-APPLICATION-TABLES"
PRODUCTION_CONFIRMATION = "SETU-PRODUCTION-RESET"


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
```

CLI behavior:

- With no `--apply`, print a read-only inventory (table names and row counts) and exit `0`.
- `--apply` requires `require_reset_confirmation`.
- Print the database host with the project reference masked, never the password or keys.
- Drop only `public` application tables; never drop `auth`, `storage`, `vault`, `realtime`, or `extensions`.
- Preserve the previous report by writing to `context/RESET_REPORT.<UTC timestamp>.md` and updating `context/RESET_REPORT.md` with a link plus the latest counts. Never hardcode a host, project ID, backup filename, or “0 remaining” claim.
- If the storage or auth query fails, report `unknown` rather than inventing a count.

Keep `cleanup_demo_data.py` as the preferred path. The reset script is an emergency tool, not the routine cleanup route.

- [ ] **Step 2: Test the guard**

```python
# backend/tests/test_reset_guard.py
import argparse

import pytest

from scripts.reset_supabase_app_data import require_reset_confirmation


def _args(**overrides):
    values = {
        "confirm": "",
        "backup": "",
        "allow_production": "",
    }
    values.update(overrides)
    return argparse.Namespace(**values)


def test_reset_refuses_without_the_exact_confirmation(tmp_path):
    backup = tmp_path / "dump.sql"
    backup.write_text("select 1;", encoding="utf-8")
    with pytest.raises(SystemExit):
        require_reset_confirmation(_args(backup=str(backup)))


def test_reset_refuses_without_a_non_empty_backup(tmp_path):
    with pytest.raises(SystemExit):
        require_reset_confirmation(_args(
            confirm="DROP-ALL-APPLICATION-TABLES",
            backup=str(tmp_path / "missing.sql"),
            allow_production="SETU-PRODUCTION-RESET",
        ))


def test_reset_refuses_without_production_acknowledgement(tmp_path):
    backup = tmp_path / "dump.sql"
    backup.write_text("select 1;", encoding="utf-8")
    with pytest.raises(SystemExit):
        require_reset_confirmation(_args(
            confirm="DROP-ALL-APPLICATION-TABLES",
            backup=str(backup),
        ))


def test_reset_accepts_all_three_gates(tmp_path):
    backup = tmp_path / "dump.sql"
    backup.write_text("select 1;", encoding="utf-8")
    require_reset_confirmation(_args(
        confirm="DROP-ALL-APPLICATION-TABLES",
        backup=str(backup),
        allow_production="SETU-PRODUCTION-RESET",
    ))
```

- [ ] **Step 3: Add the fresh-account acceptance test**

```python
# backend/tests/test_fresh_account_clean_state.py
import uuid

from app.models.profiles import UserProfile
from tests.conftest import auth_headers


def test_a_fresh_student_and_teacher_start_empty(client, db):
    student_id = uuid.uuid4()
    teacher_id = uuid.uuid4()
    db.add(UserProfile(
        id=student_id, email="fresh-student@example.com",
        display_name="Fresh Student", role="student",
    ))
    db.add(UserProfile(
        id=teacher_id, email="fresh-teacher@example.com",
        display_name="Fresh Teacher", role="teacher",
    ))
    db.commit()

    student_headers = auth_headers(student_id)
    teacher_headers = auth_headers(teacher_id)

    assert client.get("/api/v1/documents", headers=student_headers).json() == []
    assert client.get("/api/v1/learning-paths", headers=student_headers).json() == []
    assert client.get("/api/v1/doubts", headers=student_headers).json() == []
    assert client.get("/api/v1/teacher/classrooms", headers=teacher_headers).json() == []
    assert client.get("/api/v1/catalogue/resources").json() == []

    dashboard = client.get("/api/v1/profile/dashboard", headers=student_headers).json()
    assert dashboard["stats"]["totalSessions"] == 0
    assert dashboard["stats"]["totalQuestionsAttempted"] == 0
    assert dashboard["conceptMastery"] == []
    assert dashboard["recentAttempts"] == []
    assert dashboard["classrooms"] == []

    summary = client.get("/api/v1/study/summary", headers=student_headers).json()
    assert summary["minutesStudied"] == 0.0
    assert summary["checkpointCount"] == 0
    assert summary["suggestions"] == []
```

- [ ] **Step 4: Run the production-truth scans**

From the repository root:

```powershell
rg -n --glob '!**/tests/**' --glob '!**/e2e/**' "demo|mock|sample|fixture|placeholder|hardcoded|SETU-JOIN|Registered Student|default-path|GENERAL|plasma membrane|verified textbook|hallucinat|VERIFIED TEXTBOOK|Verified Answer|verified syllabus" backend/app frontend/src
rg -n "SETU V2|SETU 2\.0|2\.0\.0" frontend/src frontend/index.html frontend/vite.config.ts backend/app
rg -n "INSERT INTO resources|INSERT INTO resource_rights" backend/alembic/versions
```

Expected:

- No production `demo`, `mock`, `sample`, `fixture`, `SETU-JOIN`, `Registered Student`, `default-path`, `GENERAL`, plasma-membrane, “verified textbook”, hallucination-guarantee, or “Verified Answer” paths. Test fixtures may match; production paths may not.
- No visible version suffix or `2.0.0` in the app, manifest, or title.
- No resource or rights seed insert remains in any migration. The only matches for `resources` should be schema, delete, or read code.

If `rg` is unavailable, use:

```powershell
Get-ChildItem backend/app,frontend/src -Recurse -File |
  Select-String -Pattern 'demo|mock|sample|fixture|SETU-JOIN|Registered Student|default-path|GENERAL|plasma membrane|verified textbook|hallucinat|VERIFIED TEXTBOOK|Verified Answer|verified syllabus'
```

- [ ] **Step 5: Run the full automated verification**

```powershell
cd backend
$env:SETU_TEST_DATABASE_URL="postgresql://setu:setu_test@127.0.0.1:55432/setu_test"
.\.venv\Scripts\python -m alembic -c alembic.ini upgrade head
.\.venv\Scripts\python -m pytest tests -q
.\.venv\Scripts\python -m pytest tests -q -m "not integration"

cd ..\frontend
npm run build
npx playwright test --project=chromium
```

Expected:

- Alembic reports `head` and no pending revision.
- Unit and contract tests pass against the disposable database; integration tests are skipped unless `SETU_TEST_LLM_URL` is set.
- The frontend build succeeds with no TypeScript errors.
- All Chromium Playwright specs pass.

Record the exact summary lines, not a rounded claim. If any command fails, fix the defect or mark the affected acceptance row `Fail`/`Blocked`; do not write “all passing”.

The commands above intentionally point Alembic at the disposable database. Only after the Task 3 gate is explicitly confirmed and `cleanup_demo_data.py --apply` has finished, apply `006` and `007` to the real database from a shell that loads `backend/.env`:

```powershell
cd backend
.\.venv\Scripts\python -m alembic -c alembic.ini current
.\.venv\Scripts\python -m alembic -c alembic.ini heads
.\.venv\Scripts\python -m alembic -c alembic.ini upgrade head
```

Expected: `current` advances from `005` to `007`, and the seeded catalogue rows are gone. Do not run this before cleanup: the inventory and confirmation must happen while the seeded rows still exist. Never echo the production URL.

- [ ] **Step 6: Run the real end-to-end acceptance manually**

Start LM Studio with the configured chat and embedding models, start the backend, worker, and frontend, then use a brand-new account:

1. Sign up and complete onboarding with a real class, board, and language.
2. Confirm Home is empty: no book, no units, no minutes, no mastery, no classrooms, no recommendations.
3. Upload a small, text-based PDF that you have the right to use.
4. Watch the document move through upload → stored → extracting → indexing → awaiting_review/ready; confirm page count and chunk count are non-zero and no error is hidden.
5. Build the learning path; confirm the first ready lesson has a citation to a real page and a non-empty answer key behind the server.
6. In Learn, open a citation. In Solve, answer incorrectly and use a hint; confirm the server returns `correctAnswer` only after submission. In Test, finish the checkpoint.
7. Return to Dashboard; confirm minutes, accuracy, evidence count, and heatmap changed. Confirm the next action explains what to do next.
8. Create a teacher account and classroom; join with the student; confirm the teacher sees only that student and the concept band matches the snapshot.
9. Send a recommendation; confirm the student sees the teacher’s reason and can accept or dismiss it.
10. Ask a doubt online; confirm an answer with citations or a truthful retryable failure. Disconnect the network, ask another doubt, reconnect, and confirm it syncs once.

Record each step, the exact command or click path, and the observed result in `STATUS_REPORT.md`. If LM Studio is unavailable, mark the affected rows `Blocked — model server unavailable` and do not claim a pass.

- [ ] **Step 7: Rewrite the acceptance matrix**

Replace `context/ACCEPTANCE_MATRIX.md` with a truthful table using the same 15 flows. Allowed statuses: `Pass`, `Fail`, `Blocked`, `Not run`. For every row include:

- The exact test file or manual click path.
- The command or date of the check.
- The observed result, including counts or error text.
- Any remaining defect with an owner/next action.

Mapping:

| # | Flow | Primary evidence after this plan |
|---|---|---|
| 1 | Signup and onboarding | `tests/test_taxonomy_validation.py`, `e2e/onboarding_taxonomy.spec.ts` |
| 2 | Multi-format ingestion | `tests/test_extraction.py`, `tests/test_ingestion_quality.py`, manual upload |
| 3 | Outline review | `tests/test_learning_path_creation.py`, manual review modal |
| 4 | Eager generation and queueing | `tests/test_generation_contracts.py` |
| 5 | Worker restart recovery | `tests/test_recovery_contracts.py` |
| 6 | Grounded retrieval and citation | `tests/test_rag_evaluation.py -m integration` with a live model |
| 7 | Out-of-domain abstention | `tests/test_rag_evaluation.py -m integration`, `tests/test_doubt_truth.py` |
| 8 | Online doubt | `tests/test_doubt_truth.py`, `e2e/doubt_truth.spec.ts` |
| 9 | Offline doubt sync | `tests/test_idempotent_sync.py`, `e2e/offline_sync.spec.ts` |
| 10 | Offline lesson practice | `e2e/offline_sync.spec.ts`, manual airplane-mode check |
| 11 | Classroom and join code | `tests/test_authorization.py`, `tests/test_teacher_evidence_scope.py` |
| 12 | Teacher evidence | `tests/test_teacher_evidence_scope.py`, `e2e/teacher_evidence.spec.ts` |
| 13 | Multi-subject neutrality | `tests/test_catalogue_and_profile_defaults.py`, `tests/test_taxonomy_validation.py` |
| 14 | Failure and recovery | `tests/test_ingestion_quality.py`, `tests/test_generation_contracts.py`, `tests/test_student_dashboard_truth.py` |
| 15 | Responsive and accessible UX | `e2e/navigation_truth.spec.ts`, `e2e/student_dashboard_truth.spec.ts`, manual keyboard/mobile pass |

Do not keep the old claims “26 verified resources”, “15/15 verified”, or “0 defects” unless the current run proves them.

- [ ] **Step 8: Write the operations guide**

Create `docs/OPERATIONS.md` with:

1. Prerequisites (Python, Node, Docker, Supabase project, LM Studio).
2. Environment variable names only; never values. State that `SUPABASE_SECRET_KEY` stays server-side.
3. Install commands for `backend` and `frontend`.
4. Database migrations: `alembic current`, `alembic heads`, `alembic upgrade head`, and a warning not to edit applied revisions except the seed removal described in Task 2.
5. Disposable test database: `docker compose -f docker-compose.test.yml up -d`, `SETU_TEST_DATABASE_URL`, and the fail-closed behavior.
6. Backend and worker commands.
7. Frontend dev, build, and preview commands.
8. LM Studio model names, endpoint, and a 768-dimension embedding check.
9. Real data lifecycle: upload → storage → extraction → chunks → embeddings → retrieval → path → lesson validation; no catalogue seeds.
10. Scoped cleanup: `--inventory` first, confirm the preserved real account, then `--apply --confirm APPLY-CLEANUP`; never run the emergency reset first.
11. Emergency reset: the three gates, backup requirement, and preservation of managed schemas.
12. Backups, restore verification, and secret handling.
13. Troubleshooting: model down, OCR needed, zero chunks, failed lesson validation, auth 401/403, offline cache, migration drift.
14. Acceptance commands and links to the matrix.

- [ ] **Step 9: Update the status report and cleanup manifest**

In `STATUS_REPORT.md`, replace the old “100% passing” narrative with:

- Session date and scope.
- What changed, grouped by task, with file links.
- Exact commands and observed result lines for pytest, build, Playwright, Alembic, and the production inventory.
- Current live database counts, read-only, with the timestamp.
- The one real account and its documents, if the user confirmed preservation; otherwise mark cleanup as blocked.
- Known defects and blocked acceptance rows.
- Launch steps for a new session: test DB, backend, worker, frontend, LM Studio, and a fresh-account check.
- Explicit statement that no broad reset was run.

In `context/SUPABASE_CLEANUP_MANIFEST.md`, record the final inventory and the exact confirmation state. If `--apply` has not run, say so.

- [ ] **Step 10: Commit**

```bash
git add backend/scripts/reset_supabase_app_data.py backend/tests/test_reset_guard.py backend/tests/test_fresh_account_clean_state.py docs/OPERATIONS.md context/ACCEPTANCE_MATRIX.md STATUS_REPORT.md context/SUPABASE_CLEANUP_MANIFEST.md
git commit -m "docs: record clean-state acceptance and guard destructive reset"
```

---

## Execution Handoff

The plan is complete when all 17 tasks are checked, the fresh-account acceptance test passes against a disposable database, the production-truth scans return no fabricated paths, and the acceptance matrix contains only results observed in this session.

Two execution options:

1. **Subagent-driven (recommended):** dispatch one fresh subagent per task, review the diff and tests after each task, and keep the current session for coordination.
2. **Inline execution:** execute tasks in this session with `executing-plans`, batching commits and pausing at the cleanup confirmation gate.

The blocking human gate remains: do not run `cleanup_demo_data.py --apply` until the user confirms which profile IDs are demo accounts and which real account and documents must be preserved.





