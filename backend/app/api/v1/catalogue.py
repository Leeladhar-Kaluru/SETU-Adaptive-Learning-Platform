import uuid
from fastapi import APIRouter, Depends, Query
from typing import Optional, List
from sqlalchemy.orm import Session
from sqlalchemy import or_
from app.core.database import get_db
from app.models.curriculum import CurriculumBoard, Subject, Language, Resource, ResourceRight

router = APIRouter()

@router.get("/boards")
def list_boards(db: Session = Depends(get_db)):
    boards = db.query(CurriculumBoard).filter(CurriculumBoard.active == True).all()
    return [
        {
            "id": b.id,
            "code": b.code,
            "name": b.name,
            "region": b.region,
            "officialUrl": b.official_url
        }
        for b in boards
    ]

@router.get("/subjects")
def list_subjects(db: Session = Depends(get_db)):
    subjects = db.query(Subject).filter(Subject.active == True).all()
    return [
        {
            "id": s.id,
            "code": s.code,
            "canonicalName": s.canonical_name,
            "name": s.canonical_name
        }
        for s in subjects
    ]

@router.get("/languages")
def list_languages(db: Session = Depends(get_db)):
    languages = db.query(Language).filter(Language.active == True).all()
    return [
        {
            "id": l.id,
            "bcp47Tag": l.bcp47_tag,
            "nativeName": l.native_name,
            "script": l.script
        }
        for l in languages
    ]

@router.get("/resources")
def list_resources(
    search: Optional[str] = Query(None),
    board_id: Optional[str] = Query(None),
    grade: Optional[int] = Query(None),
    subject_id: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    query = db.query(Resource)
    if search and search.strip():
        term = f"%{search.strip()}%"
        query = query.filter(or_(Resource.title.ilike(term), Resource.publisher.ilike(term)))
    if board_id:
        query = query.filter(Resource.board_id == board_id)
    if grade:
        query = query.filter(Resource.grade == grade)
    if subject_id:
        # Match both exact ID and code (e.g. "subject-science" or "SCIENCE")
        query = query.filter(or_(Resource.subject_id == subject_id, Resource.subject_id == f"subject-{subject_id.lower()}"))

    resources = query.order_by(Resource.grade.asc(), Resource.title.asc()).all()
    
    # Load boards and subjects maps for clean display
    boards_map = {b.id: b.name for b in db.query(CurriculumBoard).all()}
    subjects_map = {s.id: s.canonical_name for s in db.query(Subject).all()}

    results = []
    for r in resources:
        subj_name = subjects_map.get(r.subject_id) or "Unknown subject"
        board_name = boards_map.get(r.board_id) or "Unknown board"

        results.append({
            "id": r.id,
            "title": r.title,
            "boardId": r.board_id,
            "board": board_name,
            "grade": r.grade,
            "subjectId": r.subject_id,
            "subject": subj_name,
            "publisher": r.publisher,
            "edition": r.edition,
            "externalUrl": r.external_url,
            "verificationStatus": r.verification_status
        })

    return results
