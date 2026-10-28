import uuid
import random
import string
import datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from sqlalchemy import func
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.security import get_current_user_id, get_current_teacher_id
from app.models.classroom import Classroom, ClassroomMembership, TeacherAction
from app.models.learning import ConceptEvidence, ConceptMasterySnapshot, QuizAttempt
from app.models.profiles import UserProfile
from app.api.v1.study import summarize_student

router = APIRouter()

JOIN_CODE_ATTEMPTS = 12


def generate_join_code(db: Session) -> Optional[str]:
    """Allocate a unique join code, or None when every attempt collided."""
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    for _ in range(JOIN_CODE_ATTEMPTS):
        code = "".join(random.choices(alphabet, k=6))
        taken = db.query(Classroom).filter(Classroom.join_code == code).first()
        if not taken:
            return code
    return None

class ClassroomCreate(BaseModel):
    name: str
    grade: int = 9
    boardId: Optional[str] = "board-cbse"
    subjectScope: str = "SCIENCE"

class JoinClassroomRequest(BaseModel):
    joinCode: str

class RecommendationCreate(BaseModel):
    classroomId: uuid.UUID
    studentId: uuid.UUID
    conceptId: str
    actionType: str
    notes: str

@router.get("/classrooms")
def list_teacher_classrooms(
    teacher_id: uuid.UUID = Depends(get_current_teacher_id),
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
    teacher_id: uuid.UUID = Depends(get_current_teacher_id),
    db: Session = Depends(get_db)
):
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
    teacher_id: uuid.UUID = Depends(get_current_teacher_id),
    db: Session = Depends(get_db)
):
    classroom = db.query(Classroom).filter(
        Classroom.id == classroom_id,
        Classroom.owner_teacher_id == teacher_id,
    ).first()
    if not classroom:
        raise HTTPException(status_code=404, detail="Classroom not found")

    memberships = db.query(ClassroomMembership).filter(
        ClassroomMembership.classroom_id == classroom_id,
        ClassroomMembership.status == "active"
    ).all()

    matrix = []
    for membership in memberships:
        profile = db.query(UserProfile).filter(UserProfile.id == membership.student_id).first()
        summary = summarize_student(db, membership.student_id)
        checks = summary["checkpointCount"]
        
        # Check actual concept mastery snapshots from adaptive engine
        snapshots = db.query(ConceptMasterySnapshot).filter(
            ConceptMasterySnapshot.owner_id == membership.student_id
        ).all()

        band = "sparse"
        if snapshots:
            bands = [s.estimate_band for s in snapshots]
            if "developing" in bands:
                band = "developing"
            elif all(b == "demonstrated" for b in bands):
                band = "demonstrated"
            elif "approaching" in bands or "demonstrated" in bands:
                band = "approaching"
            else:
                band = "sparse"
        elif summary["accuracyRate"] is not None and checks >= 1:
            acc = summary["accuracyRate"]
            if acc >= 0.85 and checks >= 2:
                band = "demonstrated"
            elif acc >= 0.65:
                band = "approaching"
            else:
                band = "developing"
        elif summary["improvement"] == "improving" and checks >= 2:
            band = "demonstrated"
        elif summary["improvement"] == "steady" and checks >= 1:
            band = "approaching"
        elif summary["improvement"] == "needs_support":
            band = "developing"

        demonstrated_count = sum(1 for s in snapshots if s.estimate_band == "demonstrated") if snapshots else (checks if band == "demonstrated" else 0)

        matrix.append({
            "studentId": str(membership.student_id),
            "studentName": profile.display_name if profile else "Student",
            "conceptsDemonstrated": demonstrated_count,
            "totalConcepts": len(snapshots) if snapshots else checks,
            "accuracyRate": summary["accuracyRate"] if summary["accuracyRate"] is not None else 0,
            "accuracyKnown": summary["accuracyRate"] is not None,
            "recentAttemptsCount": checks,
            "evidenceBand": band,
            "lastActive": next((day["date"] for day in reversed(summary["heatmap"]) if day["seconds"] > 0), ""),
            "minutesStudied": summary["minutesStudied"],
            "readingTitle": summary["readingTitle"],
            "improvement": summary["improvement"],
            "heatmap": summary["heatmap"],
            "pace": summary["pace"],
            "focus": summary["focus"],
        })

    # Collect teacher recommendations
    actions = db.query(TeacherAction).filter(TeacherAction.classroom_id == classroom_id).order_by(TeacherAction.created_at.desc()).all()

    return {
        "classroomId": str(classroom.id),
        "name": classroom.name,
        "grade": classroom.grade,
        "subjectScope": classroom.subject_scope,
        "joinCode": classroom.join_code,
        "totalStudents": len(matrix),
        "matrix": matrix,
        "students": matrix,
        "actions": [
            {
                "id": str(a.id),
                "studentId": str(a.student_id),
                "actionType": a.action_type,
                "notes": a.reason_json.get("notes") if a.reason_json else "",
                "conceptId": a.reason_json.get("conceptId") if a.reason_json else "",
                "status": a.status,
                "createdAt": a.created_at.isoformat()
            }
            for a in actions
        ]
    }

@router.get("/evidence")
def get_teacher_evidence(
    grade: Optional[int] = Query(9),
    subject: Optional[str] = Query("SCIENCE"),
    teacher_id: uuid.UUID = Depends(get_current_teacher_id),
    db: Session = Depends(get_db)
):
    """
    Returns aggregated concept evidence matrix for the teacher's grade and subject.
    """
    # Fetch real concept evidence records
    evidences = db.query(ConceptEvidence).all()
    concept_map: Dict[str, Dict[str, Any]] = {}

    for ev in evidences:
        cid = ev.concept_id
        if cid not in concept_map:
            concept_map[cid] = {
                "conceptId": cid,
                "conceptName": cid.replace("sci-", "").replace("math-", "").replace("-", " ").title(),
                "totalAttempts": 0,
                "correctAttempts": 0,
                "lastAssessedAt": ev.created_at.strftime("%Y-%m-%d")
            }
        concept_map[cid]["totalAttempts"] += 1
        if ev.outcome == "correct":
            concept_map[cid]["correctAttempts"] += 1

    results = []
    for cid, data in concept_map.items():
        tot = data["totalAttempts"]
        cor = data["correctAttempts"]
        acc = (cor / tot) if tot > 0 else 0.0
        band = "demonstrated" if acc >= 0.8 and tot >= 3 else ("approaching" if acc >= 0.6 else "developing" if tot >= 2 else "sparse")
        results.append({
            "conceptId": cid,
            "conceptName": data["conceptName"],
            "totalAttempts": tot,
            "correctAttempts": cor,
            "accuracyRate": round(acc, 2),
            "masteryBand": band,
            "lastAssessedAt": data["lastAssessedAt"]
        })

    return results

@router.post("/recommendations")
@router.post("/actions")
def create_recommendation(
    req: RecommendationCreate,
    teacher_id: uuid.UUID = Depends(get_current_teacher_id),
    db: Session = Depends(get_db)
):
    """Creates an actionable pedagogical recommendation from a teacher."""
    classroom = db.query(Classroom).filter(
        Classroom.id == req.classroomId,
        Classroom.owner_teacher_id == teacher_id,
    ).first()
    if not classroom:
        raise HTTPException(status_code=404, detail="Classroom not found")
    member = db.query(ClassroomMembership).filter(
        ClassroomMembership.classroom_id == classroom.id,
        ClassroomMembership.student_id == req.studentId,
        ClassroomMembership.status == "active",
    ).first()
    if not member:
        raise HTTPException(status_code=404, detail="That student is not in this classroom.")

    action = TeacherAction(
        teacher_id=teacher_id,
        classroom_id=classroom.id,
        student_id=req.studentId,
        action_type=req.actionType,
        reason_json={
            "conceptId": req.conceptId,
            "notes": req.notes,
        },
        status="active"
    )
    db.add(action)
    db.commit()
    db.refresh(action)

    return {
        "id": str(action.id),
        "status": action.status,
        "actionType": action.action_type,
        "conceptId": req.conceptId,
        "notes": req.notes
    }
