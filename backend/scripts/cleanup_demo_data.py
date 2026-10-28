"""Scoped demo-data inventory and cleanup for SETU.

The default ``--inventory`` mode is strictly read-only. ``--apply`` is gated by
an explicit confirmation token and explicit delete/preserve user IDs.

Only application tables in the ``public`` schema are touched. The ``auth``,
``storage`` and other managed schemas are never modified by :func:`cleanup`.
Auth users are deleted only when the CLI is given ``--delete-auth-users`` and
the operator has supplied the confirmation token; the helper logs IDs only.
"""
from __future__ import annotations

import argparse
import asyncio
import datetime as dt
import json
import re
import sys
import uuid
from pathlib import Path
from typing import Any, Callable, Iterable, Optional

BACKEND_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_DIR.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from sqlalchemy import or_, select, text  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.core.database import SessionLocal  # noqa: E402
from app.core.storage import storage_service  # noqa: E402
from app.models.classroom import (  # noqa: E402
    Classroom,
    ClassroomMembership,
    TeacherAction,
)
from app.models.curriculum import Resource, ResourceRight  # noqa: E402
from app.models.documents import Document, DocumentChunk, DocumentPage  # noqa: E402
from app.models.doubts import Doubt, SyncEvent  # noqa: E402
from app.models.jobs import GenerationJob  # noqa: E402
from app.models.learning import (  # noqa: E402
    ConceptEvidence,
    ConceptMasterySnapshot,
    LearningPath,
    LessonVersion,
    PathLesson,
    Question,
    QuizAttempt,
    StudyEvent,
)
from app.models.profiles import UserProfile  # noqa: E402

CONFIRM_TOKEN = "APPLY-CLEANUP"
REPORT_PATH = REPO_ROOT / "context" / "CLEANUP_REPORT.md"
DOCUMENT_BUCKET = "setu-documents"

# Kept in sync with backend/alembic/versions/006_remove_seeded_catalogue_and_profile_defaults.py.
# The cleanup re-applies the same removal as a safety net for databases where
# migration 006 has not run yet.
SEEDED_RESOURCE_IDS: tuple[str, ...] = (
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

TEST_EMAIL_DOMAINS = {
    "example.com",
    "example.org",
    "example.net",
    "example.test",
    "test.com",
    "localhost",
    "invalid",
}

# Tables shown in the report. The first column is the key returned by inventory().
INVENTORY_ORDER: tuple[tuple[str, str], ...] = (
    ("profiles", "user_profiles"),
    ("documents", "documents"),
    ("document_pages", "document_pages"),
    ("document_chunks", "document_chunks"),
    ("learning_paths", "learning_paths"),
    ("path_lessons", "path_lessons"),
    ("lesson_versions", "lesson_versions"),
    ("questions", "questions"),
    ("quiz_attempts", "quiz_attempts"),
    ("concept_evidence", "concept_evidence"),
    ("concept_mastery_snapshots", "concept_mastery_snapshots"),
    ("doubts", "doubts"),
    ("sync_events", "sync_events"),
    ("classrooms", "classrooms"),
    ("classroom_memberships", "classroom_memberships"),
    ("teacher_actions", "teacher_actions"),
    ("study_events", "study_events"),
    ("generation_jobs", "generation_jobs"),
    ("resources", "resources"),
    ("resource_rights", "resource_rights"),
)


def mask_email(email: Optional[str]) -> str:
    """Return a stable masked form; the local part is never fully exposed."""
    if not email or "@" not in email:
        return "***"
    local, domain = email.rsplit("@", 1)
    if not local:
        return f"***@{domain}"
    return f"{local[0]}***@{domain}"


def email_domain(email: Optional[str]) -> str:
    if not email or "@" not in email:
        return "unknown"
    return email.rsplit("@", 1)[1].strip().lower() or "unknown"


def is_test_domain(domain: str) -> bool:
    domain = (domain or "").strip().lower()
    return (
        domain in TEST_EMAIL_DOMAINS
        or domain.endswith(".test")
        or domain.endswith(".invalid")
        or domain.endswith(".example")
    )


def _count(db: Session, model: Any) -> int:
    return int(db.query(model).count())


def inventory(
    db: Session,
    *,
    list_storage_objects: Optional[Callable[[], Any]] = None,
) -> dict[str, Any]:
    """Return counts and masked identity metadata. This function never writes."""
    profile_rows = (
        db.query(
            UserProfile.id,
            UserProfile.email,
            UserProfile.role,
            UserProfile.created_at,
        )
        .order_by(UserProfile.created_at.asc().nulls_last(), UserProfile.id.asc())
        .all()
    )

    users: list[dict[str, Any]] = []
    profiles_by_domain: dict[str, int] = {}
    for row in profile_rows:
        domain = email_domain(row.email)
        profiles_by_domain[domain] = profiles_by_domain.get(domain, 0) + 1
        users.append(
            {
                "id": str(row.id),
                "email": mask_email(row.email),
                "domain": domain,
                "is_test_domain": is_test_domain(domain),
                "role": row.role,
                "created_at": row.created_at.isoformat() if row.created_at else None,
            }
        )

    storage_objects: Optional[int] = None
    if list_storage_objects is not None:
        try:
            storage_result = list_storage_objects()
            if isinstance(storage_result, int):
                storage_objects = storage_result
            elif isinstance(storage_result, dict) and "count" in storage_result:
                storage_objects = int(storage_result["count"])
            elif storage_result is not None:
                storage_objects = len(storage_result)
        except Exception:
            # A storage probe failure must never invent a count or abort inventory.
            storage_objects = None

    counts = {
        "profiles": len(profile_rows),
        "profiles_by_domain": dict(sorted(profiles_by_domain.items())),
        "documents": _count(db, Document),
        "document_pages": _count(db, DocumentPage),
        "document_chunks": _count(db, DocumentChunk),
        "learning_paths": _count(db, LearningPath),
        "path_lessons": _count(db, PathLesson),
        "lesson_versions": _count(db, LessonVersion),
        "questions": _count(db, Question),
        "quiz_attempts": _count(db, QuizAttempt),
        "concept_evidence": _count(db, ConceptEvidence),
        "concept_mastery_snapshots": _count(db, ConceptMasterySnapshot),
        "doubts": _count(db, Doubt),
        "sync_events": _count(db, SyncEvent),
        "classrooms": _count(db, Classroom),
        "classroom_memberships": _count(db, ClassroomMembership),
        "teacher_actions": _count(db, TeacherAction),
        "study_events": _count(db, StudyEvent),
        "generation_jobs": _count(db, GenerationJob),
        "resources": _count(db, Resource),
        "resource_rights": _count(db, ResourceRight),
        "storage_objects": None,
        "users": users,
    }

    # Probe storage only after all database counts have been read. A failed probe
    # (or a probe that aborts a shared transaction) must not hide database counts.
    if list_storage_objects is not None:
        try:
            storage_result = list_storage_objects()
            if isinstance(storage_result, int):
                counts["storage_objects"] = storage_result
            elif isinstance(storage_result, dict) and "count" in storage_result:
                counts["storage_objects"] = int(storage_result["count"])
            elif storage_result is not None:
                counts["storage_objects"] = len(storage_result)
        except Exception:
            # A storage probe failure must never invent a count or abort inventory.
            counts["storage_objects"] = None

    return counts


def _coerce_user_ids(values: Iterable[uuid.UUID | str], label: str) -> set[uuid.UUID]:
    result: set[uuid.UUID] = set()
    for value in values or ():
        if isinstance(value, uuid.UUID):
            result.add(value)
            continue
        try:
            result.add(uuid.UUID(str(value)))
        except (TypeError, ValueError) as exc:
            raise ValueError(f"Invalid {label} user ID: {value!r}") from exc
    return result


def _delete_scoped(
    db: Session,
    model: Any,
    condition: Any,
    *,
    apply: bool,
) -> int:
    """Count, then (when applying) delete rows matching the condition."""
    query = db.query(model).filter(condition)
    count = int(query.count())
    if apply and count:
        query.delete(synchronize_session="fetch")
    return count


def cleanup(
    db: Session,
    *,
    delete_user_ids: set[uuid.UUID],
    preserve_user_ids: set[uuid.UUID],
    apply: bool,
    delete_storage_object: Optional[Callable[[str, str], bool]] = None,
) -> dict[str, Any]:
    """Delete data for exactly the named users.

    ``delete_user_ids`` and ``preserve_user_ids`` must be disjoint. An empty
    delete set is refused when ``apply`` is true. ``auth.users`` is never
    touched by this function regardless of its arguments.
    """
    delete_ids = _coerce_user_ids(delete_user_ids, "delete")
    preserve_ids = _coerce_user_ids(preserve_user_ids, "preserve")
    apply = bool(apply)

    overlap = delete_ids & preserve_ids
    if overlap:
        ids = ", ".join(sorted(str(value) for value in overlap))
        raise ValueError(
            "Refusing cleanup: the same user IDs cannot be deleted and preserved: "
            f"{ids}"
        )
    if apply and not delete_ids:
        raise ValueError(
            "Refusing cleanup: --apply requires at least one explicitly named user to delete."
        )

    result: dict[str, Any] = {
        "applied": apply,
        "delete_user_ids": sorted(str(value) for value in delete_ids),
        "preserve_user_ids": sorted(str(value) for value in preserve_ids),
        "storage_deleted": 0,
        "storage_failed": 0,
        "deleted_users": 0,
        "preserved_users": 0,
        "cleared_document_resource_references": 0,
    }
    counts: dict[str, int] = {}

    # Snapshot parent/child relationships before any rows are removed. These
    # subqueries are evaluated by PostgreSQL at delete time while the parents
    # still exist, and they keep the deletes FK-safe if a child row is owned by
    # a different profile.
    deleted_path_ids = select(LearningPath.id).where(
        LearningPath.owner_id.in_(delete_ids)
    )
    deleted_lesson_ids = select(PathLesson.id).where(
        PathLesson.path_id.in_(deleted_path_ids)
    )
    deleted_version_ids = select(LessonVersion.id).where(
        LessonVersion.path_lesson_id.in_(deleted_lesson_ids)
    )
    deleted_question_ids = select(Question.id).where(
        Question.lesson_version_id.in_(deleted_version_ids)
    )
    deleted_classroom_ids = select(Classroom.id).where(
        Classroom.owner_teacher_id.in_(delete_ids)
    )
    deleted_attempt_ids = select(QuizAttempt.id).where(
        or_(
            QuizAttempt.owner_id.in_(delete_ids),
            QuizAttempt.lesson_version_id.in_(deleted_version_ids),
            QuizAttempt.question_id.in_(deleted_question_ids),
        )
    )
    deleted_document_ids = select(Document.id).where(
        Document.owner_id.in_(delete_ids)
    )

    # Storage deletion happens before database rows are removed. Failures are
    # recorded but never abort the database cleanup.
    documents = (
        db.query(Document)
        .filter(Document.owner_id.in_(delete_ids))
        .order_by(Document.id.asc())
        .all()
    )
    if apply:
        for document in documents:
            if delete_storage_object is None:
                result["storage_failed"] += 1
                continue
            try:
                deleted = delete_storage_object(
                    document.storage_bucket or DOCUMENT_BUCKET,
                    document.storage_key,
                )
            except Exception:
                result["storage_failed"] += 1
            else:
                if deleted:
                    result["storage_deleted"] += 1
                else:
                    result["storage_failed"] += 1

    # FK-safe deletion order. Children before parents.
    counts["teacher_actions"] = _delete_scoped(
        db,
        TeacherAction,
        or_(
            TeacherAction.teacher_id.in_(delete_ids),
            TeacherAction.student_id.in_(delete_ids),
            TeacherAction.classroom_id.in_(deleted_classroom_ids),
        ),
        apply=apply,
    )
    counts["classroom_memberships"] = _delete_scoped(
        db,
        ClassroomMembership,
        or_(
            ClassroomMembership.student_id.in_(delete_ids),
            ClassroomMembership.classroom_id.in_(deleted_classroom_ids),
        ),
        apply=apply,
    )
    counts["classrooms"] = _delete_scoped(
        db,
        Classroom,
        Classroom.owner_teacher_id.in_(delete_ids),
        apply=apply,
    )
    counts["sync_events"] = _delete_scoped(
        db,
        SyncEvent,
        SyncEvent.owner_id.in_(delete_ids),
        apply=apply,
    )
    counts["doubts"] = _delete_scoped(
        db,
        Doubt,
        Doubt.owner_id.in_(delete_ids),
        apply=apply,
    )
    counts["concept_evidence"] = _delete_scoped(
        db,
        ConceptEvidence,
        or_(
            ConceptEvidence.owner_id.in_(delete_ids),
            ConceptEvidence.source_attempt_id.in_(deleted_attempt_ids),
        ),
        apply=apply,
    )
    counts["concept_mastery_snapshots"] = _delete_scoped(
        db,
        ConceptMasterySnapshot,
        ConceptMasterySnapshot.owner_id.in_(delete_ids),
        apply=apply,
    )
    counts["quiz_attempts"] = _delete_scoped(
        db,
        QuizAttempt,
        or_(
            QuizAttempt.owner_id.in_(delete_ids),
            QuizAttempt.lesson_version_id.in_(deleted_version_ids),
            QuizAttempt.question_id.in_(deleted_question_ids),
        ),
        apply=apply,
    )
    counts["study_events"] = _delete_scoped(
        db,
        StudyEvent,
        StudyEvent.owner_id.in_(delete_ids),
        apply=apply,
    )
    counts["generation_jobs"] = _delete_scoped(
        db,
        GenerationJob,
        or_(
            GenerationJob.owner_id.in_(delete_ids),
            GenerationJob.path_id.in_(deleted_path_ids),
        ),
        apply=apply,
    )

    # Counts for rows removed by ON DELETE CASCADE before their parents go.
    counts["path_lessons"] = int(
        db.query(PathLesson).filter(PathLesson.path_id.in_(deleted_path_ids)).count()
    )
    counts["lesson_versions"] = int(
        db.query(LessonVersion)
        .filter(LessonVersion.path_lesson_id.in_(deleted_lesson_ids))
        .count()
    )
    counts["questions"] = int(
        db.query(Question)
        .filter(Question.lesson_version_id.in_(deleted_version_ids))
        .count()
    )
    counts["document_pages"] = int(
        db.query(DocumentPage)
        .filter(DocumentPage.document_id.in_(deleted_document_ids))
        .count()
    )
    counts["document_chunks"] = int(
        db.query(DocumentChunk)
        .filter(DocumentChunk.document_id.in_(deleted_document_ids))
        .count()
    )

    counts["learning_paths"] = _delete_scoped(
        db,
        LearningPath,
        LearningPath.owner_id.in_(delete_ids),
        apply=apply,
    )
    counts["documents"] = _delete_scoped(
        db,
        Document,
        Document.owner_id.in_(delete_ids),
        apply=apply,
    )
    counts["user_profiles"] = _delete_scoped(
        db,
        UserProfile,
        UserProfile.id.in_(delete_ids),
        apply=apply,
    )

    # Safety net for the 26 seeded catalogue resources. Clear references from
    # documents that are staying (for example, a real user's document), then
    # remove rights and resources. This never touches taxonomy tables.
    seeded_ref_count = int(
        db.query(Document)
        .filter(Document.resource_id.in_(SEEDED_RESOURCE_IDS))
        .count()
    )
    if apply:
        result["cleared_document_resource_references"] = int(
            db.query(Document)
            .filter(Document.resource_id.in_(SEEDED_RESOURCE_IDS))
            .update({Document.resource_id: None}, synchronize_session=False)
        )
    else:
        result["cleared_document_resource_references"] = seeded_ref_count

    counts["resource_rights"] = _delete_scoped(
        db,
        ResourceRight,
        ResourceRight.resource_id.in_(SEEDED_RESOURCE_IDS),
        apply=apply,
    )
    counts["resources"] = _delete_scoped(
        db,
        Resource,
        Resource.id.in_(SEEDED_RESOURCE_IDS),
        apply=apply,
    )

    result["deleted_users"] = counts["user_profiles"] if apply else 0
    result["preserved_users"] = int(
        db.query(UserProfile).filter(UserProfile.id.in_(preserve_ids)).count()
    ) if preserve_ids else 0
    result["deleted_counts"] = dict(counts)
    result.update(counts)

    if apply:
        db.commit()

    return result


def _profiles_for_ids(
    db: Session, user_ids: set[uuid.UUID]
) -> dict[uuid.UUID, tuple[Optional[str], Optional[str]]]:
    if not user_ids:
        return {}
    rows = (
        db.query(UserProfile.id, UserProfile.email, UserProfile.role)
        .filter(UserProfile.id.in_(user_ids))
        .all()
    )
    return {row.id: (row.email, row.role) for row in rows}


def _storage_object_count() -> Optional[int]:
    """Read-only count of storage objects; never mutates the storage schema."""
    session = SessionLocal()
    try:
        row = session.execute(
            text(
                "SELECT COUNT(*) FROM storage.objects WHERE bucket_id = :bucket"
            ),
            {"bucket": settings.STORAGE_BUCKET_DOCUMENTS},
        ).scalar_one()
        return int(row)
    except Exception:
        return None
    finally:
        session.close()


def _delete_storage_object(bucket: str, path: str) -> bool:
    return bool(asyncio.run(storage_service.delete_file(bucket, path)))


def _delete_auth_users(user_ids: set[uuid.UUID]) -> dict[str, Any]:
    """Delete auth users through the Supabase Admin API, logging IDs only.

    This is only reachable when ``--delete-auth-users`` is explicitly passed to
    an apply run. The default inventory and cleanup paths never call it.
    """
    import httpx

    base = settings.SUPABASE_URL
    if base and not base.startswith("http"):
        base = f"https://{base}"
    base = (base or "").rstrip("/")
    if not base or not settings.SUPABASE_SECRET_KEY:
        return {
            "deleted": [],
            "failed": [str(value) for value in sorted(user_ids, key=str)],
            "error": "Supabase admin credentials are not configured.",
        }

    headers = {
        "apikey": settings.SUPABASE_SECRET_KEY,
        "Authorization": f"Bearer {settings.SUPABASE_SECRET_KEY}",
    }
    deleted: list[str] = []
    failed: list[dict[str, Any]] = []
    with httpx.Client(timeout=20.0) as client:
        for user_id in sorted(user_ids, key=str):
            try:
                response = client.delete(
                    f"{base}/auth/v1/admin/users/{user_id}", headers=headers
                )
            except Exception as exc:
                failed.append({"id": str(user_id), "error": _sanitize_error(exc)})
                continue
            if response.status_code in (200, 204):
                deleted.append(str(user_id))
            else:
                # Never log the response body; it can echo account details.
                failed.append({"id": str(user_id), "status": response.status_code})
    return {"deleted": deleted, "failed": failed}


def _sanitize_error(exc: BaseException) -> str:
    message = f"{type(exc).__name__}: {exc}"
    message = re.sub(
        r"(?:postgres(?:ql)?|https?)://[^\s'\"]+",
        "[redacted-url]",
        message,
        flags=re.IGNORECASE,
    )
    message = re.sub(
        r"(?:password|apikey|api_key|secret|token)\s*[=:]\s*[^\s,;]+",
        "[redacted-secret]",
        message,
        flags=re.IGNORECASE,
    )
    message = re.sub(
        r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}",
        "[redacted-email]",
        message,
    )
    return message[:600]


def _inventory_table_rows(data: dict[str, Any]) -> list[str]:
    lines = ["| Table | Count |", "|---|---:|"]
    for key, table in INVENTORY_ORDER:
        lines.append(f"| `{table}` | {data.get(key, 'n/a')} |")
    lines.append(
        f"| `storage.objects` (`{DOCUMENT_BUCKET}`) | "
        f"{data.get('storage_objects') if data.get('storage_objects') is not None else 'unavailable'} |"
    )
    return lines


def _inventory_user_rows(data: dict[str, Any]) -> list[str]:
    lines = [
        "| User ID | Masked email | Domain | Test-domain heuristic | Role | Created |",
        "|---|---|---|---|---|---|",
    ]
    for user in data.get("users", []):
        lines.append(
            "| `{id}` | `{email}` | `{domain}` | {test} | {role} | {created} |".format(
                id=user.get("id", ""),
                email=user.get("email", "***"),
                domain=user.get("domain", "unknown"),
                test="yes" if user.get("is_test_domain") else "no",
                role=user.get("role") or "",
                created=user.get("created_at") or "",
            )
        )
    return lines


def _render_inventory_report(data: dict[str, Any]) -> str:
    now = dt.datetime.now(dt.timezone.utc).isoformat()
    lines = [
        "# SETU — Scoped Demo-Data Cleanup Report",
        "",
        f"**Generated:** {now}",
        "**Database:** configured database connection (URL and keys are never printed)",
        "**Mode:** `--inventory` (read-only)",
        "**Status:** INVENTORY COMPLETE",
        "",
        "## Inventory",
        "",
        *_inventory_table_rows(data),
        "",
        f"**Profiles by domain:** `{json.dumps(data.get('profiles_by_domain', {}), sort_keys=True)}`",
        "",
        "## User Profiles (masked)",
        "",
        *_inventory_user_rows(data),
        "",
        "## Confirmation Gate",
        "",
        "- **Status: OPEN**",
        "- `--apply` was not run.",
        "- No rows were deleted.",
        "- No storage objects were deleted.",
        "- `auth.users` were not touched.",
        "- Applying requires `--confirm APPLY-CLEANUP`, at least one "
        "`--delete-user-id`, and at least one `--preserve-user-id`.",
        "",
        "The inventory is a read-only observation. It does not assert that every "
        "`example.com` profile is disposable; a human must name the demo users and "
        "the real `gmail.com` account before any apply run.",
        "",
    ]
    return "\n".join(lines)


def _render_apply_report(
    before: dict[str, Any],
    result: dict[str, Any],
    after: dict[str, Any],
    profiles: dict[uuid.UUID, tuple[Optional[str], Optional[str]]],
    auth_result: Optional[dict[str, Any]],
) -> str:
    now = dt.datetime.now(dt.timezone.utc).isoformat()
    lines = [
        "# SETU — Scoped Demo-Data Cleanup Report",
        "",
        f"**Generated:** {now}",
        "**Database:** configured database connection (URL and keys are never printed)",
        "**Mode:** `--apply`",
        "**Status:** APPLIED",
        "",
        "## Confirmed Users",
        "",
        "### Deleted",
        "",
        "| User ID | Masked email |",
        "|---|---|",
    ]
    for user_id in result.get("delete_user_ids", []):
        email, _role = profiles.get(uuid.UUID(user_id), (None, None))
        lines.append(f"| `{user_id}` | `{mask_email(email)}` |")
    lines.extend(
        [
            "",
            "### Preserved",
            "",
            "| User ID | Masked email |",
            "|---|---|",
        ]
    )
    for user_id in result.get("preserve_user_ids", []):
        email, _role = profiles.get(uuid.UUID(user_id), (None, None))
        lines.append(f"| `{user_id}` | `{mask_email(email)}` |")

    lines.extend(
        [
            "",
            "## Cleanup Counts",
            "",
            "| Table | Deleted rows |",
            "|---|---:|",
        ]
    )
    for key, table in INVENTORY_ORDER:
        lines.append(f"| `{table}` | {result.get('deleted_counts', {}).get(table, 0)} |")
    lines.extend(
        [
            "",
            f"- Profiles deleted: **{result.get('deleted_users', 0)}**",
            f"- Preserved profiles still present: **{result.get('preserved_users', 0)}**",
            f"- Storage objects deleted: **{result.get('storage_deleted', 0)}**",
            f"- Storage deletion failures: **{result.get('storage_failed', 0)}**",
            f"- Document resource references cleared: "
            f"**{result.get('cleared_document_resource_references', 0)}**",
            "",
            "## Before / After",
            "",
            "| Table | Before | After |",
            "|---|---:|---:|",
        ]
    )
    for key, table in INVENTORY_ORDER:
        lines.append(
            f"| `{table}` | {before.get(key, 'n/a')} | {after.get(key, 'n/a')} |"
        )

    if auth_result is not None:
        lines.extend(
            [
                "",
                "## Auth Users",
                "",
                f"- Deleted auth user IDs: {', '.join(auth_result.get('deleted', [])) or 'none'}",
                f"- Failed auth user IDs: "
                f"{', '.join(item.get('id', '') for item in auth_result.get('failed', [])) or 'none'}",
            ]
        )
    else:
        lines.extend(
            [
                "",
                "## Auth Users",
                "",
                "- `auth.users` were not touched by this run.",
            ]
        )

    lines.append("")
    return "\n".join(lines)


def _render_failure_report(mode: str, error: str) -> str:
    now = dt.datetime.now(dt.timezone.utc).isoformat()
    return "\n".join(
        [
            "# SETU — Scoped Demo-Data Cleanup Report",
            "",
            f"**Generated:** {now}",
            "**Database:** configured database connection (URL and keys are never printed)",
            f"**Mode:** `{mode}`",
            "**Status:** FAILED",
            "",
            "## Result",
            "",
            f"- Error: `{error}`",
            "- No counts are reported because the database could not be read.",
            "- No rows were deleted by this failed run.",
            "- Confirmation gate remains **OPEN**.",
            "",
        ]
    )


def _write_report(content: str) -> Path:
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(content, encoding="utf-8")
    return REPORT_PATH


def _print_users(
    title: str,
    user_ids: set[uuid.UUID],
    profiles: dict[uuid.UUID, tuple[Optional[str], Optional[str]]],
) -> None:
    print(title)
    for user_id in sorted(user_ids, key=str):
        email, role = profiles.get(user_id, (None, None))
        print(f"  - {user_id}  {mask_email(email)}  role={role or 'unknown'}")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Inventory or apply the scoped SETU demo-data cleanup. "
            "Inventory is read-only. Apply requires an explicit confirmation token."
        )
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--inventory", action="store_true", help="read-only inventory")
    mode.add_argument("--apply", action="store_true", help="delete data for named users")
    parser.add_argument(
        "--delete-user-id",
        action="append",
        default=[],
        type=uuid.UUID,
        help="profile UUID to delete; repeat for each demo account",
    )
    parser.add_argument(
        "--preserve-user-id",
        action="append",
        default=[],
        type=uuid.UUID,
        help="profile UUID that must survive; repeat for each real account",
    )
    parser.add_argument(
        "--delete-auth-users",
        action="store_true",
        help="also delete the named auth users through the Supabase Admin API",
    )
    parser.add_argument("--confirm", default="", help=f"must equal {CONFIRM_TOKEN} for --apply")
    return parser


def main(argv: Optional[list[str]] = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    delete_ids = set(args.delete_user_id or [])
    preserve_ids = set(args.preserve_user_id or [])

    if args.apply:
        if args.confirm != CONFIRM_TOKEN:
            parser.error(f"--apply requires --confirm {CONFIRM_TOKEN}")
        if not delete_ids:
            parser.error("--apply requires at least one --delete-user-id")
        if not preserve_ids:
            parser.error("--apply requires at least one --preserve-user-id")
        overlap = delete_ids & preserve_ids
        if overlap:
            parser.error(
                "a user ID cannot be both deleted and preserved: "
                + ", ".join(sorted(str(value) for value in overlap))
            )
    elif args.delete_auth_users:
        parser.error("--delete-auth-users is only valid with --apply")

    db = SessionLocal()
    try:
        if args.inventory:
            data = inventory(db, list_storage_objects=_storage_object_count)
            print("SETU scoped cleanup inventory (read-only)")
            print(json.dumps(data, indent=2, default=str))
            report_path = _write_report(_render_inventory_report(data))
            print(f"\nReport written to {report_path}")
            return 0

        before = inventory(db, list_storage_objects=_storage_object_count)
        profiles = _profiles_for_ids(db, delete_ids | preserve_ids)
        missing = (delete_ids | preserve_ids) - set(profiles)
        if missing:
            parser.error(
                "unknown user profile ID(s): "
                + ", ".join(sorted(str(value) for value in missing))
            )

        print("SETU scoped cleanup — apply mode")
        _print_users("Users to delete:", delete_ids, profiles)
        _print_users("Users to preserve:", preserve_ids, profiles)

        result = cleanup(
            db,
            delete_user_ids=delete_ids,
            preserve_user_ids=preserve_ids,
            apply=True,
            delete_storage_object=_delete_storage_object,
        )

        auth_result = None
        if args.delete_auth_users:
            auth_result = _delete_auth_users(delete_ids)

        after = inventory(db, list_storage_objects=_storage_object_count)
        print(json.dumps(result, indent=2, default=str))
        report_path = _write_report(
            _render_apply_report(before, result, after, profiles, auth_result)
        )
        print(f"Report written to {report_path}")
        return 0
    except Exception as exc:
        error = _sanitize_error(exc)
        mode = "apply" if args.apply else "inventory"
        _write_report(_render_failure_report(mode, error))
        print(f"ERROR: {error}", file=sys.stderr)
        return 1
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
