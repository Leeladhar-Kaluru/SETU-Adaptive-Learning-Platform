import datetime
import uuid
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user_id
from app.models.classroom import Classroom, ClassroomMembership, ClassroomMessage
from app.models.profiles import UserProfile

router = APIRouter()


class SendMessageRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    body: str = Field(min_length=1, max_length=2000)
    kind: str = Field(default="group")  # group | direct
    recipient_id: Optional[uuid.UUID] = Field(default=None, alias="recipientId")


def _classroom_access(db: Session, classroom_id: uuid.UUID, user_id: uuid.UUID) -> tuple[Classroom, str]:
    classroom = db.query(Classroom).filter(Classroom.id == classroom_id).first()
    if classroom is None:
        raise HTTPException(status_code=404, detail="Classroom not found.")
    if classroom.owner_teacher_id == user_id:
        return classroom, "teacher"
    membership = (
        db.query(ClassroomMembership)
        .filter(
            ClassroomMembership.classroom_id == classroom_id,
            ClassroomMembership.student_id == user_id,
            ClassroomMembership.status == "active",
        )
        .first()
    )
    if membership is None:
        raise HTTPException(status_code=404, detail="Classroom not found.")
    return classroom, membership.role or "student"


def _display_names(db: Session, user_ids: List[uuid.UUID]) -> Dict[str, str]:
    if not user_ids:
        return {}
    rows = db.query(UserProfile.id, UserProfile.display_name).filter(UserProfile.id.in_(user_ids)).all()
    return {str(row[0]): row[1] for row in rows}


def _message_payload(msg: ClassroomMessage, names: Dict[str, str]) -> Dict[str, Any]:
    return {
        "id": str(msg.id),
        "classroomId": str(msg.classroom_id),
        "senderId": str(msg.sender_id),
        "senderName": names.get(str(msg.sender_id), "Member"),
        "kind": msg.kind,
        "recipientId": str(msg.recipient_id) if msg.recipient_id else None,
        "body": msg.body,
        "createdAt": msg.created_at.isoformat() if msg.created_at else None,
    }


@router.get("/me")
def my_classrooms(
    owner_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    memberships = (
        db.query(ClassroomMembership)
        .filter(
            ClassroomMembership.student_id == owner_id,
            ClassroomMembership.status == "active",
        )
        .all()
    )
    owned = db.query(Classroom).filter(Classroom.owner_teacher_id == owner_id).all()
    classrooms: List[Dict[str, Any]] = []
    seen: set = set()
    teacher_ids: List[uuid.UUID] = []
    for classroom in owned:
        seen.add(classroom.id)
        teacher_ids.append(classroom.owner_teacher_id)
        classrooms.append(
            {
                "id": str(classroom.id),
                "name": classroom.name,
                "grade": classroom.grade,
                "subjectScope": classroom.subject_scope,
                "boardId": classroom.board_id,
                "role": "teacher",
                "joinCode": classroom.join_code,
            }
        )
    for membership in memberships:
        classroom = db.query(Classroom).filter(Classroom.id == membership.classroom_id).first()
        if classroom is None or classroom.id in seen:
            continue
        seen.add(classroom.id)
        teacher_ids.append(classroom.owner_teacher_id)
        classrooms.append(
            {
                "id": str(classroom.id),
                "name": classroom.name,
                "grade": classroom.grade,
                "subjectScope": classroom.subject_scope,
                "boardId": classroom.board_id,
                "role": membership.role or "student",
                "joinCode": None,
            }
        )
    teacher_names = _display_names(db, teacher_ids)
    for entry in classrooms:
        classroom = (
            db.query(Classroom)
            .filter(Classroom.id == uuid.UUID(entry["id"]))
            .first()
        )
        if classroom is not None:
            entry["teacherId"] = str(classroom.owner_teacher_id)
            entry["teacherName"] = teacher_names.get(str(classroom.owner_teacher_id), "Teacher")
    return {"classrooms": classrooms}


@router.get("/{classroom_id}/messages")
def list_messages(
    classroom_id: uuid.UUID,
    after: Optional[datetime.datetime] = Query(default=None),
    owner_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    classroom, role = _classroom_access(db, classroom_id, owner_id)
    query = db.query(ClassroomMessage).filter(ClassroomMessage.classroom_id == classroom_id)
    if role != "teacher":
        query = query.filter(
            (ClassroomMessage.kind == "group")
            | (ClassroomMessage.sender_id == owner_id)
            | (ClassroomMessage.recipient_id == owner_id)
        )
    if after is not None:
        query = query.filter(ClassroomMessage.created_at > after)
    messages = query.order_by(ClassroomMessage.created_at.asc()).limit(200).all()
    user_ids = {msg.sender_id for msg in messages}
    names = _display_names(db, list(user_ids))
    return {"messages": [_message_payload(msg, names) for msg in messages]}


@router.post("/{classroom_id}/messages")
def send_message(
    classroom_id: uuid.UUID,
    req: SendMessageRequest,
    owner_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    classroom, role = _classroom_access(db, classroom_id, owner_id)
    body = " ".join(req.body.split()).strip()
    if not body:
        raise HTTPException(status_code=422, detail="Message cannot be empty.")
    kind = "direct" if req.kind == "direct" else "group"
    recipient_id = req.recipient_id
    if kind == "direct":
        if recipient_id is None:
            raise HTTPException(status_code=422, detail="recipientId is required for a direct message.")
        if recipient_id == owner_id:
            raise HTTPException(status_code=422, detail="You cannot message yourself.")
        valid_recipient = classroom.owner_teacher_id == recipient_id
        if not valid_recipient and role == "teacher":
            valid_recipient = (
                db.query(ClassroomMembership)
                .filter(
                    ClassroomMembership.classroom_id == classroom_id,
                    ClassroomMembership.student_id == recipient_id,
                    ClassroomMembership.status == "active",
                )
                .first()
                is not None
            )
        if not valid_recipient:
            raise HTTPException(status_code=404, detail="Recipient is not part of this classroom.")
    msg = ClassroomMessage(
        classroom_id=classroom_id,
        sender_id=owner_id,
        kind=kind,
        recipient_id=recipient_id if kind == "direct" else None,
        body=body[:2000],
        created_at=datetime.datetime.now(datetime.timezone.utc),
    )
    db.add(msg)
    db.commit()
    names = _display_names(db, [owner_id])
    return {"message": _message_payload(msg, names)}
