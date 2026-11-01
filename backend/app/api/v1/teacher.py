import uuid
import random
import datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from typing import Optional, Literal, Dict, Any
from sqlalchemy import func
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.security import get_current_educator_id, get_current_user_id
from app.models.classroom import Classroom, ClassroomMembership, TeacherAction
from app.models.curriculum import CurriculumBoard, Subject
from app.models.learning import ConceptEvidence, ConceptMasterySnapshot
from app.models.profiles import UserProfile
from app.api.v1.study import summarize_student

router = APIRouter()

JOIN_CODE_ATTEMPTS = 12
EVIDENCE_RANK = {"not_enough_evidence": -1, "developing": 0, "approaching": 1, "demonstrated": 2}


def generate_join_code(db: Session) -> Optional[str]:
    """Allocate a unique join code, or None when every attempt collided."""
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    for _ in range(JOIN_CODE_ATTEMPTS):
        code = "".join(random.choices(alphabet, k=6))
        taken = db.query(Classroom).filter(Classroom.join_code == code).first()
        if not taken:
            return code
    return None


def _owned_classroom(db: Session, classroom_id: uuid.UUID, teacher_id: uuid.UUID) -> Classroom:
    classroom = db.query(Classroom).filter(
        Classroom.id == classroom_id,
        Classroom.owner_teacher_id == teacher_id,
    ).first()
    if not classroom:
        raise HTTPException(status_code=404, detail="Classroom not found")
    return classroom


def _active_member_ids(db: Session, classroom_id: uuid.UUID) -> list[uuid.UUID]:
    return [
        row[0]
        for row in db.query(ClassroomMembership.student_id).filter(
            ClassroomMembership.classroom_id == classroom_id,
            ClassroomMembership.status == "active",
        ).all()
    ]


class ClassroomCreate(BaseModel):
    name: str = Field(min_length=2, max_length=150)
    grade: int = Field(ge=6, le=10)
    boardId: str
    subjectScope: str

class JoinClassroomRequest(BaseModel):
    joinCode: str = Field(min_length=1, max_length=20)

class RecommendationCreate(BaseModel):
    classroomId: uuid.UUID
    studentId: uuid.UUID
    conceptId: str = Field(min_length=1, max_length=100)
    actionType: Literal["reinforce_foundations", "advance_challenge", "targeted_review"]
    notes: str = Field(min_length=3, max_length=1000)


class RosterUpdate(BaseModel):
    status: Literal["active", "removed"]


class TeacherActionDecision(BaseModel):
    decision: Literal["accept", "dismiss", "override"]
    notes: Optional[str] = Field(default=None, max_length=500)

@router.get("/classrooms")
def list_teacher_classrooms(
    teacher_id: uuid.UUID = Depends(get_current_educator_id),
    db: Session = Depends(get_db)
):
    classrooms = db.query(Classroom).filter(Classroom.owner_teacher_id == teacher_id).all()

    results = []
    for c in classrooms:
        member_count = db.query(ClassroomMembership).filter(
            ClassroomMembership.classroom_id == c.id,
            ClassroomMembership.status == "active"
        ).count()
        results.append({
            "id": str(c.id),
            "name": c.name,
            "grade": c.grade,
            "boardId": c.board_id,
            "subjectScope": c.subject_scope,
            "joinCode": c.join_code,
            "memberCount": member_count,
            "createdAt": c.created_at.isoformat()
        })
    return results

@router.post("/classrooms")
def create_classroom(
    req: ClassroomCreate,
    teacher_id: uuid.UUID = Depends(get_current_educator_id),
    db: Session = Depends(get_db)
):
    board = db.query(CurriculumBoard).filter(
        CurriculumBoard.id == req.boardId,
        CurriculumBoard.active.is_(True),
    ).first()
    if not board:
        raise HTTPException(status_code=422, detail="Choose a curriculum board from the list.")
    subject = db.query(Subject).filter(
        Subject.id == req.subjectScope,
        Subject.active.is_(True),
    ).first()
    if not subject:
        raise HTTPException(status_code=422, detail="Choose an available subject from the list.")

    join_code = generate_join_code(db)
    if join_code is None:
        raise HTTPException(
            status_code=503,
            detail="Could not allocate a unique classroom code. Try again.",
        )
    cr = Classroom(
        owner_teacher_id=teacher_id,
        name=req.name.strip(),
        grade=req.grade,
        board_id=req.boardId,
        subject_scope=req.subjectScope,
        join_code=join_code
    )
    db.add(cr)
    db.commit()
    db.refresh(cr)
    return {
        "id": str(cr.id),
        "name": cr.name,
        "grade": cr.grade,
        "subjectScope": cr.subject_scope,
        "joinCode": cr.join_code,
        "createdAt": cr.created_at.isoformat()
    }

@router.get("/classrooms/{classroom_id}/roster")
def get_classroom_roster(
    classroom_id: uuid.UUID,
    teacher_id: uuid.UUID = Depends(get_current_educator_id),
    db: Session = Depends(get_db),
):
    """Authorized roster for one owned classroom, including removed memberships."""
    classroom = _owned_classroom(db, classroom_id, teacher_id)
    memberships = (
        db.query(ClassroomMembership)
        .filter(ClassroomMembership.classroom_id == classroom.id)
        .order_by(ClassroomMembership.created_at.asc())
        .all()
    )
    profiles = {}
    student_ids = [membership.student_id for membership in memberships]
    if student_ids:
        profiles = {
            profile.id: profile
            for profile in db.query(UserProfile).filter(UserProfile.id.in_(student_ids)).all()
        }

    return {
        "classroomId": str(classroom.id),
        "joinCode": classroom.join_code,
        "members": [
            {
                "studentId": str(membership.student_id),
                "studentName": (
                    profiles[membership.student_id].display_name
                    if membership.student_id in profiles
                    else "Account removed"
                ),
                "profileMissing": membership.student_id not in profiles,
                "status": membership.status,
                "joinedAt": membership.created_at.isoformat() if membership.created_at else None,
            }
            for membership in memberships
        ],
    }


@router.post("/classrooms/{classroom_id}/rotate-join-code")
def rotate_join_code(
    classroom_id: uuid.UUID,
    teacher_id: uuid.UUID = Depends(get_current_educator_id),
    db: Session = Depends(get_db),
):
    """Issues a fresh join code and invalidates the previous one."""
    classroom = _owned_classroom(db, classroom_id, teacher_id)
    join_code = generate_join_code(db)
    if join_code is None:
        raise HTTPException(
            status_code=503,
            detail="Could not allocate a unique classroom code. Try again.",
        )
    classroom.join_code = join_code
    db.commit()
    db.refresh(classroom)
    return {"classroomId": str(classroom.id), "joinCode": classroom.join_code}


@router.patch("/classrooms/{classroom_id}/members/{student_id}")
def update_classroom_member(
    classroom_id: uuid.UUID,
    student_id: uuid.UUID,
    req: RosterUpdate,
    teacher_id: uuid.UUID = Depends(get_current_educator_id),
    db: Session = Depends(get_db),
):
    """Removes or restores one real membership without touching other classrooms."""
    classroom = _owned_classroom(db, classroom_id, teacher_id)
    membership = db.query(ClassroomMembership).filter(
        ClassroomMembership.classroom_id == classroom.id,
        ClassroomMembership.student_id == student_id,
    ).first()
    if not membership:
        raise HTTPException(status_code=404, detail="That student has not joined this classroom.")

    membership.status = req.status
    db.commit()
    return {
        "classroomId": str(classroom.id),
        "studentId": str(membership.student_id),
        "status": membership.status,
    }


@router.post("/join")
def join_classroom(
    req: JoinClassroomRequest,
    student_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    """Allows student to join a real teacher's classroom via join code."""
    code = req.joinCode.strip().upper()
    classroom = db.query(Classroom).filter(
        func.upper(Classroom.join_code) == code
    ).first()
    if not classroom:
        raise HTTPException(status_code=404, detail="Invalid classroom code. Please check with your teacher.")

    existing = db.query(ClassroomMembership).filter(
        ClassroomMembership.classroom_id == classroom.id,
        ClassroomMembership.student_id == student_id
    ).first()

    classroom_payload = {
        "id": str(classroom.id),
        "name": classroom.name,
        "grade": classroom.grade,
        "subjectScope": classroom.subject_scope,
        "joinCode": classroom.join_code,
    }
    if existing:
        if existing.status == "removed":
            raise HTTPException(
                status_code=403,
                detail="Your membership in this classroom was removed. Ask your teacher to restore it.",
            )
        return {
            "success": True,
            "status": "already_member",
            "classroomId": str(classroom.id),
            "classroom": classroom_payload,
            "membership": {"status": existing.status},
        }

    membership = ClassroomMembership(
        classroom_id=classroom.id,
        student_id=student_id,
        role="student",
        status="active"
    )
    db.add(membership)
    db.commit()

    return {
        "success": True,
        "status": "joined",
        "classroomId": str(classroom.id),
        "classroom": classroom_payload,
        "membership": {"status": "active"},
    }

@router.get("/classrooms/{classroom_id}/evidence-matrix")
def get_classroom_evidence_matrix(
    classroom_id: uuid.UUID,
    teacher_id: uuid.UUID = Depends(get_current_educator_id),
    db: Session = Depends(get_db)
):
    classroom = _owned_classroom(db, classroom_id, teacher_id)

    memberships = db.query(ClassroomMembership).filter(
        ClassroomMembership.classroom_id == classroom_id,
        ClassroomMembership.status == "active"
    ).all()

    matrix = []
    for membership in memberships:
        profile = db.query(UserProfile).filter(UserProfile.id == membership.student_id).first()
        summary = summarize_student(db, membership.student_id)

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
        evidence_band = (
            "not_enough_evidence"
            if not concepts
            else min((item["band"] for item in concepts), key=lambda band: EVIDENCE_RANK.get(band, -1))
        )
        concepts_demonstrated = sum(1 for item in concepts if item["band"] == "demonstrated")
        accuracy_known = summary["accuracyRate"] is not None

        matrix.append({
            "studentId": str(membership.student_id),
            "studentName": profile.display_name if profile else "Account removed",
            "profileMissing": profile is None,
            "concepts": concepts,
            "conceptsDemonstrated": concepts_demonstrated,
            "totalConcepts": len(concepts),
            "accuracyRate": summary["accuracyRate"] if accuracy_known else 0,
            "accuracyKnown": accuracy_known,
            "recentAttemptsCount": summary["checkpointCount"],
            "evidenceBand": evidence_band,
            "lastActive": next(
                (day["date"] for day in reversed(summary["heatmap"]) if day["seconds"] > 0),
                "",
            ),
            "minutesStudied": summary["minutesStudied"],
            "readingTitle": summary["readingTitle"],
            "improvement": summary["improvement"],
            "heatmap": summary["heatmap"],
            "pace": summary["pace"],
            "focus": summary["focus"],
        })

    actions = (
        db.query(TeacherAction)
        .filter(TeacherAction.classroom_id == classroom_id)
        .order_by(TeacherAction.created_at.desc())
        .all()
    )

    # Class-level gap radar: aggregate only the snapshots of active members.
    gap_map: Dict[str, Dict[str, Any]] = {}
    for row in matrix:
        for concept in row["concepts"]:
            bucket = gap_map.setdefault(
                concept["conceptId"],
                {
                    "conceptId": concept["conceptId"],
                    "studentsWithEvidence": 0,
                    "bands": {
                        "demonstrated": 0,
                        "approaching": 0,
                        "developing": 0,
                        "not_enough_evidence": 0,
                    },
                    "scores": [],
                    "studentsNeedingSupport": [],
                },
            )
            bucket["studentsWithEvidence"] += 1
            bucket["bands"][concept["band"]] = bucket["bands"].get(concept["band"], 0) + 1
            if concept.get("score") is not None:
                bucket["scores"].append(concept["score"])
            if concept["band"] in ("developing", "not_enough_evidence"):
                bucket["studentsNeedingSupport"].append(row["studentName"])

    class_gaps = []
    for bucket in gap_map.values():
        average = (
            round(sum(bucket["scores"]) / len(bucket["scores"]), 1)
            if bucket["scores"]
            else None
        )
        need_support = len(bucket["studentsNeedingSupport"])
        class_gaps.append(
            {
                "conceptId": bucket["conceptId"],
                "studentsWithEvidence": bucket["studentsWithEvidence"],
                "averageScore": average,
                "bands": bucket["bands"],
                "studentsNeedingSupport": need_support,
                "supportNames": bucket["studentsNeedingSupport"][:8],
                "priority": (
                    bucket["bands"].get("developing", 0) * 3
                    + bucket["bands"].get("not_enough_evidence", 0)
                    + need_support
                ),
            }
        )
    class_gaps.sort(key=lambda item: (-item["priority"], item["conceptId"]))

    return {
        "classroomId": str(classroom.id),
        "name": classroom.name,
        "grade": classroom.grade,
        "subjectScope": classroom.subject_scope,
        "joinCode": classroom.join_code,
        "totalStudents": len(matrix),
        "matrix": matrix,
        "students": matrix,
        "classGaps": class_gaps,
        "actions": [
            {
                "id": str(a.id),
                "studentId": str(a.student_id),
                "actionType": a.action_type,
                "notes": (a.reason_json or {}).get("notes") or "",
                "conceptId": (a.reason_json or {}).get("conceptId") or "",
                "status": a.status,
                "studentResponse": (a.reason_json or {}).get("studentResponse"),
                "createdAt": a.created_at.isoformat() if a.created_at else None,
            }
            for a in actions
        ]
    }

@router.get("/evidence")
def get_teacher_evidence(
    classroom_id: uuid.UUID = Query(..., alias="classroomId"),
    teacher_id: uuid.UUID = Depends(get_current_educator_id),
    db: Session = Depends(get_db),
):
    """Concept evidence aggregated only from the members of one owned classroom."""
    classroom = _owned_classroom(db, classroom_id, teacher_id)
    member_ids = _active_member_ids(db, classroom.id)
    if not member_ids:
        return []

    evidences = (
        db.query(ConceptEvidence)
        .filter(ConceptEvidence.owner_id.in_(member_ids))
        .all()
    )
    concept_map: Dict[str, Dict[str, Any]] = {}
    for evidence in evidences:
        row = concept_map.setdefault(
            evidence.concept_id,
            {
                "conceptId": evidence.concept_id,
                "totalAttempts": 0,
                "correctAttempts": 0,
                "incorrectAttempts": 0,
                "lastAssessedAt": None,
            },
        )
        row["totalAttempts"] += 1
        if evidence.outcome == "correct":
            row["correctAttempts"] += 1
        elif evidence.outcome == "incorrect":
            row["incorrectAttempts"] += 1
        occurred = evidence.occurred_at.isoformat() if evidence.occurred_at else None
        if occurred and (row["lastAssessedAt"] is None or occurred > row["lastAssessedAt"]):
            row["lastAssessedAt"] = occurred

    return [concept_map[concept_id] for concept_id in sorted(concept_map)]

@router.post("/recommendations")
@router.post("/actions")
def create_recommendation(
    req: RecommendationCreate,
    teacher_id: uuid.UUID = Depends(get_current_educator_id),
    db: Session = Depends(get_db)
):
    """Creates an explained recommendation backed by a real mastery snapshot."""
    classroom = _owned_classroom(db, req.classroomId, teacher_id)
    member = db.query(ClassroomMembership).filter(
        ClassroomMembership.classroom_id == classroom.id,
        ClassroomMembership.student_id == req.studentId,
        ClassroomMembership.status == "active",
    ).first()
    if not member:
        raise HTTPException(status_code=404, detail="That student is not in this classroom.")

    snapshot = (
        db.query(ConceptMasterySnapshot)
        .filter(
            ConceptMasterySnapshot.owner_id == req.studentId,
            ConceptMasterySnapshot.concept_id == req.conceptId,
        )
        .order_by(ConceptMasterySnapshot.calculated_at.desc())
        .first()
    )
    if not snapshot:
        raise HTTPException(
            status_code=422,
            detail="No evidence exists for that topic in this classroom yet.",
        )

    now = datetime.datetime.utcnow()
    previous = db.query(TeacherAction).filter(
        TeacherAction.classroom_id == classroom.id,
        TeacherAction.student_id == req.studentId,
        TeacherAction.status == "proposed",
    ).all()
    for action in previous:
        reason = dict(action.reason_json or {})
        if reason.get("conceptId") == req.conceptId:
            action.status = "superseded"
            action.resolved_at = now

    reason_json = {
        "source": "teacher",
        "conceptId": req.conceptId,
        "notes": req.notes.strip(),
        "evidence": {
            "band": snapshot.estimate_band,
            "score": round((snapshot.numeric_estimate or 0.0) * 100, 1),
            "evidenceCount": snapshot.evidence_count,
            "calculatedAt": snapshot.calculated_at.isoformat() if snapshot.calculated_at else None,
        },
    }
    action = TeacherAction(
        teacher_id=teacher_id,
        classroom_id=classroom.id,
        student_id=req.studentId,
        action_type=req.actionType,
        status="proposed",
        reason_json=reason_json,
    )
    db.add(action)
    db.commit()
    db.refresh(action)

    return {
        "id": str(action.id),
        "status": action.status,
        "actionType": action.action_type,
        "conceptId": req.conceptId,
        "notes": reason_json["notes"],
        "reason": reason_json,
    }


@router.patch("/actions/{action_id}")
def decide_teacher_action(
    action_id: uuid.UUID,
    req: TeacherActionDecision,
    teacher_id: uuid.UUID = Depends(get_current_educator_id),
    db: Session = Depends(get_db),
):
    """Teacher-side accept, dismiss, or override of a recommendation."""
    action = db.query(TeacherAction).filter(
        TeacherAction.id == action_id,
        TeacherAction.teacher_id == teacher_id,
    ).first()
    if not action:
        raise HTTPException(status_code=404, detail="Recommendation not found.")
    if action.status == "superseded":
        raise HTTPException(
            status_code=409,
            detail="This recommendation was replaced by a newer one.",
        )

    notes = (req.notes or "").strip()
    if req.decision == "override" and len(notes) < 3:
        raise HTTPException(
            status_code=422,
            detail="Explain the override so the student understands the change.",
        )

    status_by_decision = {
        "accept": "accepted",
        "dismiss": "dismissed",
        "override": "edited",
    }
    action.status = status_by_decision[req.decision]
    action.resolved_at = datetime.datetime.utcnow()
    reason = dict(action.reason_json or {})
    reason["teacherDecision"] = {
        "decision": req.decision,
        "notes": notes[:500],
        "decidedAt": action.resolved_at.isoformat(),
    }
    action.reason_json = reason
    db.commit()
    db.refresh(action)

    return {
        "id": str(action.id),
        "classroomId": str(action.classroom_id),
        "studentId": str(action.student_id),
        "actionType": action.action_type,
        "status": action.status,
        "decision": req.decision,
        "notes": notes[:500],
    }
