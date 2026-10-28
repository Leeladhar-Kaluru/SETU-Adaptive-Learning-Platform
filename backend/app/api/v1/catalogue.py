from fastapi import APIRouter, Depends, Query
from typing import Optional, List
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models.curriculum import CurriculumBoard, Subject, Language, Resource, ResourceRight

router = APIRouter()

@router.get("/boards")
def list_boards(db: Session = Depends(get_db)):
    return db.query(CurriculumBoard).filter(CurriculumBoard.active == True).all()

@router.get("/subjects")
def list_subjects(db: Session = Depends(get_db)):
    return db.query(Subject).filter(Subject.active == True).all()

@router.get("/languages")
def list_languages(db: Session = Depends(get_db)):
    return db.query(Language).filter(Language.active == True).all()

@router.get("/resources")
def list_resources(
    board_id: Optional[str] = Query(None),
    grade: Optional[int] = Query(None),
    subject_id: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    query = db.query(Resource)
    if board_id:
        query = query.filter(Resource.board_id == board_id)
    if grade:
        query = query.filter(Resource.grade == grade)
    if subject_id:
        query = query.filter(Resource.subject_id == subject_id)
    
    resources = query.all()
    results = []
    for r in resources:
        rights = db.query(ResourceRight).filter(ResourceRight.resource_id == r.id).first()
        results.append({
            "id": r.id,
            "title": r.title,
            "boardId": r.board_id,
            "grade": r.grade,
            "subjectId": r.subject_id,
            "publisher": r.publisher,
            "edition": r.edition,
            "externalUrl": r.external_url,
            "verificationStatus": r.verification_status,
            "rights": {
                "licenseName": rights.license_name if rights else "Unknown",
                "canDownload": rights.can_download if rights else False,
                "canStore": rights.can_store if rights else False,
                "canProcess": rights.can_process if rights else False,
                "canOfflineCache": rights.can_offline_cache if rights else False
            } if rights else None
        })
    return results
