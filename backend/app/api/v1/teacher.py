import uuid
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.security import get_current_teacher_id
from app.models.classroom import Classroom, ClassroomMembership, TeacherAction
from app.models.learning import ConceptEvidence, ConceptMasterySnapshot

router = APIRouter()

class TeacherActionCreate(BaseModel):
    classroom_id: uuid.UUID
    student_id: uuid.UUID
    action_type: str
    reason: Dict[str, Any]

@router.get("/classrooms")
def list_teacher_classrooms(
    teacher_id: uuid.UUID = Depends(get_current_teacher_id),
    db: Session = Depends(get_db)
):
    classrooms = db.query(Classroom).filter(Classroom.owner_teacher_id == teacher_id).all()
    if not classrooms:
        # Create a real default classroom for the verified teacher if none exists
        default_cr = Classroom(
            owner_teacher_id=teacher_id,
            name="Class 9 Science Section A",
            board_id="board-cbse",
            grade=9,
            subject_scope="SCIENCE"
        )
        db.add(default_cr)
        db.commit()
        db.refresh(default_cr)
        classrooms = [default_cr]

    return [
        {
            "id": str(c.id),
            "name": c.name,
            "grade": c.grade,
            "boardId": c.board_id,
            "subjectScope": c.subject_scope,
            "createdAt": c.created_at.isoformat()
        }
        for c in classrooms
    ]

@router.get("/classrooms/{classroom_id}/evidence-matrix")
def get_classroom_evidence_matrix(
    classroom_id: uuid.UUID,
    teacher_id: uuid.UUID = Depends(get_current_teacher_id),
    db: Session = Depends(get_db)
):
    classroom = db.query(Classroom).filter(
        Classroom.id == classroom_id,
        Classroom.owner_teacher_id == teacher_id
    ).first()
    if not classroom:
        raise HTTPException(status_code=404, detail="Classroom not found or access denied")

    memberships = db.query(ClassroomMembership).filter(
        ClassroomMembership.classroom_id == classroom_id,
        ClassroomMembership.status == "active"
    ).all()

    # Collect student mastery snapshots
    matrix = []
    for m in memberships:
        snapshots = db.query(ConceptMasterySnapshot).filter(ConceptMasterySnapshot.owner_id == m.student_id).all()
        matrix.append({
            "studentId": str(m.student_id),
            "role": m.role,
            "concepts": [
                {
                    "conceptId": s.concept_id,
                    "band": s.estimate_band,
                    "score": s.numeric_estimate,
                    "evidenceCount": s.evidence_count,
                    "explanation": s.explanation_json.get("explanation") if s.explanation_json else None
                }
                for s in snapshots
            ]
        })

    # Actionable interventions based on real evidence
    recommendations = []
    actions = db.query(TeacherAction).filter(TeacherAction.classroom_id == classroom_id).all()

    return {
        "classroomId": str(classroom.id),
        "name": classroom.name,
        "grade": classroom.grade,
        "matrix": matrix,
        "actions": [
            {
                "id": str(a.id),
                "studentId": str(a.student_id),
                "actionType": a.action_type,
                "reason": a.reason_json,
                "status": a.status
            }
            for a in actions
        ]
    }

@router.post("/actions")
def create_teacher_action(
    req: TeacherActionCreate,
    teacher_id: uuid.UUID = Depends(get_current_teacher_id),
    db: Session = Depends(get_db)
):
    action = TeacherAction(
        teacher_id=teacher_id,
        classroom_id=req.classroom_id,
        student_id=req.student_id,
        action_type=req.action_type,
        reason_json=req.reason,
        status="proposed"
    )
    db.add(action)
    db.commit()
    db.refresh(action)
    return {"id": str(action.id), "status": action.status}
