"""Directly exercise lesson generation against the live provider."""
import asyncio
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import SessionLocal
from app.models.documents import Document, DocumentChunk
from app.models.learning import LearningPath, PathLesson
from app.services.lesson_generator import lesson_generator_service


async def main():
    db = SessionLocal()
    path = db.query(LearningPath).first()
    lesson = (
        db.query(PathLesson)
        .filter(PathLesson.path_id == path.id)
        .order_by(PathLesson.sequence.asc())
        .first()
    )
    document = db.query(Document).filter(Document.id == path.document_id).first()
    chapters = (path.outline_json or {}).get("chapters", [])
    chapter = chapters[max(0, lesson.sequence - 1)]
    chunks = (
        db.query(DocumentChunk)
        .filter(
            DocumentChunk.document_id == path.document_id,
            DocumentChunk.page_start <= chapter["pageEnd"],
            DocumentChunk.page_end >= chapter["pageStart"],
        )
        .order_by(DocumentChunk.chunk_index.asc())
        .all()
    )
    evidence = [
        {
            "citationId": f"cite_{str(chunk.id)[:8]}",
            "chunkId": str(chunk.id),
            "documentVersionId": str(chunk.document_id),
            "pageStart": chunk.page_start,
            "pageEnd": chunk.page_end,
            "headingPath": chunk.heading_path or [],
            "sourceTitle": document.original_filename,
            "text": chunk.text,
        }
        for chunk in chunks
    ]
    print(f"lesson={lesson.id} title={lesson.title!r} chunks={len(evidence)}")
    started = time.monotonic()
    package = await lesson_generator_service.generate_lesson_package(
        lesson_id=lesson.lesson_key,
        lesson_title=lesson.title,
        path_id=str(path.id),
        grade=path.grade,
        subject=path.subject_id,
        evidence_chunks=evidence,
    )
    elapsed = round(time.monotonic() - started, 2)
    print(f"elapsed={elapsed}s status={package['validation']['status']}")
    for check in package["validation"]["checks"]:
        print(f"  {check['name']}: {check['passed']} ({check['details']})")
    print(f"blocks={len(package.get('blocks', []))} visuals={len(package.get('visuals', []))}")
    print(f"practice={len(package.get('practice', []))} checkpoint={len(package.get('checkpointTest', []))}")
    print(f"sourceRefs={[(ref['pageStart'], ref['headingPath']) for ref in package.get('sourceRefs', [])]}")
    db.close()


if __name__ == "__main__":
    asyncio.run(main())
