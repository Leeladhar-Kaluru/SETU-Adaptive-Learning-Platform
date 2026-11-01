import re
import uuid
import datetime
import logging
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from app.models.documents import Document, DocumentChunk
from app.models.doubts import Doubt
from app.models.learning import LearningPath
from app.models.profiles import UserProfile
from app.services.retrieval import retrieval_service
from app.services.text_sanitize import sanitize_prose
from app.core.ai_provider import ai_provider

logger = logging.getLogger(__name__)

_QUESTION_STOPWORDS = {
    "about", "after", "again", "also", "answer", "because", "been", "before",
    "being", "between", "both", "called", "could", "does", "doing", "down",
    "during", "each", "from", "have", "having", "here", "into", "just", "like",
    "make", "many", "more", "most", "much", "must", "only", "other", "over",
    "same", "should", "some", "such", "than", "that", "their", "them", "then",
    "there", "these", "they", "this", "those", "through", "under", "very",
    "want", "what", "when", "where", "which", "while", "with", "would", "your",
}


def _content_tokens(text: str) -> set[str]:
    tokens = set()
    for raw in re.findall(r"[a-z0-9]+", (text or "").lower()):
        if len(raw) < 4 or raw in _QUESTION_STOPWORDS:
            continue
        tokens.add(raw[:-1] if raw.endswith("s") and len(raw) > 4 else raw)
    return tokens


def select_supporting_citations(
    results: List[Dict[str, Any]], question_text: str
) -> List[Dict[str, Any]]:
    """Keeps the best passage plus passages that actually share question terms.

    Retrieval can return a nearby-but-unrelated chapter because vector
    distance alone is permissive. Citations must not imply that an unrelated
    page supports the answer, so extra passages need real term overlap.
    """
    if not results:
        return []
    question_tokens = _content_tokens(question_text)
    threshold = 2 if len(question_tokens) >= 4 else 1
    selected: List[Dict[str, Any]] = []
    for index, row in enumerate(results):
        overlap = len(question_tokens & _content_tokens(row.get("text") or ""))
        if index == 0 or overlap >= threshold:
            selected.append(row)
    return selected


def _student_language(db: Session, owner_id: uuid.UUID) -> str:
    profile = (
        db.query(UserProfile.preferred_language)
        .filter(UserProfile.id == owner_id)
        .first()
    )
    language = (profile[0] if profile else None) or "en"
    return language.strip()[:20]


class SyncService:
    async def sync_doubt(
        self,
        db: Session,
        owner_id: uuid.UUID,
        client_doubt_id: str,
        question_text: str,
        path_id: Optional[uuid.UUID] = None,
        lesson_version_id: Optional[uuid.UUID] = None,
        block_id: Optional[str] = None,
        source_page: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Idempotent doubt intake. An answered doubt is returned as-is. A doubt
        that previously failed is retried instead of replayed forever.
        """
        existing = db.query(Doubt).filter(
            Doubt.owner_id == owner_id,
            Doubt.client_doubt_id == client_doubt_id
        ).first()

        if existing and existing.status == "answered":
            return {
                "id": str(existing.id),
                "clientDoubtId": existing.client_doubt_id,
                "status": existing.status,
                "questionText": existing.question_text,
                "answerJson": existing.answer_json,
                "alreadyExisted": True
            }

        already_existed = existing is not None
        if existing:
            doubt = existing
            doubt.status = "processing"
            doubt.last_error_code = None
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

        try:
            # 1. Resolve path and document context.
            # If path_id is provided, look up its document.
            # If not provided, fall back to the student's active learning path or latest uploaded document
            # so Ask SETU retains full textbook context across all app pages.
            document_id = None
            path = None
            if path_id:
                path = db.query(LearningPath).filter(
                    LearningPath.id == path_id,
                    LearningPath.owner_id == owner_id,
                ).first()
                if path and path.document_id:
                    document_id = path.document_id

            if not path:
                active_path = (
                    db.query(LearningPath)
                    .filter(LearningPath.owner_id == owner_id, LearningPath.status != "archived")
                    .order_by(LearningPath.created_at.desc())
                    .first()
                )
                if active_path:
                    path = active_path
                    path_id = active_path.id
                    if not document_id:
                        document_id = active_path.document_id

            if not document_id:
                latest_doc = (
                    db.query(Document)
                    .filter(Document.owner_id == owner_id, Document.deleted_at.is_(None))
                    .order_by(Document.created_at.desc())
                    .first()
                )
                if latest_doc:
                    document_id = latest_doc.id

            if not document_id:
                fallback_doc = (
                    db.query(Document)
                    .filter(Document.deleted_at.is_(None), Document.status.in_(["awaiting_review", "ready"]))
                    .order_by(Document.created_at.desc())
                    .first()
                )
                if fallback_doc:
                    document_id = fallback_doc.id

            if not path and document_id:
                path = (
                    db.query(LearningPath)
                    .filter(LearningPath.document_id == document_id, LearningPath.status != "archived")
                    .order_by(LearningPath.created_at.desc())
                    .first()
                )

            if path_id and not doubt.path_id:
                doubt.path_id = path_id

            reply_language = _student_language(db, owner_id)

            # If user has no documents uploaded at all, provide general academic tutoring
            if not document_id:
                general_prompt = (
                    "You are the SETU Academic Tutor for a school student.\n"
                    "Answer clearly, warmly, and concisely (under 130 words) in plain language, without a greeting.\n"
                    "Never write LaTeX, raw math symbols, or awkward formatting.\n"
                    "The student has not uploaded any study material yet. Answer their question clearly from general academic knowledge.\n"
                    "If they are asking about an uploaded document, politely inform them that no textbook has been uploaded yet, and invite them to upload one on the dashboard to unlock page-grounded explanations.\n"
                    f"Reply in the student's preferred language (language code: {reply_language}).\n"
                    f"Student Question: {question_text}\n"
                )
                llm_answer = await ai_provider.generate_chat(
                    messages=[{"role": "user", "content": general_prompt}],
                    temperature=0.3,
                    max_tokens=900,
                    require_complete=True,
                )
                if not llm_answer or not str(llm_answer).strip():
                    raise RuntimeError("empty tutor response")
                answer_payload = {
                    "answer": sanitize_prose(llm_answer),
                    "citations": [],
                    "limitations": "general_knowledge",
                    "answeredAt": datetime.datetime.utcnow().isoformat(),
                }
                doubt.status = "answered"
                doubt.last_error_code = None
                doubt.answer_json = answer_payload
                doubt.answered_at = datetime.datetime.utcnow()
                db.commit()
                db.refresh(doubt)
                return {
                    "id": str(doubt.id),
                    "clientDoubtId": doubt.client_doubt_id,
                    "status": doubt.status,
                    "questionText": doubt.question_text,
                    "answerJson": doubt.answer_json,
                    "alreadyExisted": already_existed,
                }

            # Document is present — fetch document record
            doc = db.query(Document).filter(Document.id == document_id).first()
            doc_title = doc.original_filename if doc else "Uploaded Textbook"

            # Check if student is asking for a summary/overview of the uploaded document/book
            q_lower = question_text.lower().strip()
            summary_triggers = [
                "summary", "summarize", "overview", "what is this book",
                "about the document", "uploaded document", "uploaded material",
                "table of contents", "outline", "syllabus", "what does this book cover",
                "what did i upload", "chapters", "explain the book", "brief of document"
            ]
            is_summary_request = any(t in q_lower for t in summary_triggers)

            if is_summary_request:
                # Build high-level curriculum outline from LearningPath outline_json if available
                chapters_list = []
                if path and path.outline_json and isinstance(path.outline_json, dict):
                    chapters_list = path.outline_json.get("chapters", [])

                chapters_str = ""
                if chapters_list:
                    chapters_str = "\n".join(
                        f"- {ch.get('title', 'Chapter')} (pp. {ch.get('pageStart', '?')}-{ch.get('pageEnd', '?')})"
                        for ch in chapters_list[:12]
                    )

                # Fetch early chunks / intro context from the document
                intro_chunks = (
                    db.query(DocumentChunk)
                    .filter(DocumentChunk.document_id == document_id)
                    .order_by(DocumentChunk.page_start.asc(), DocumentChunk.chunk_index.asc())
                    .limit(3)
                    .all()
                )
                intro_str = "\n".join(
                    f"- Page {c.page_start}: {c.text[:400]}"
                    for c in intro_chunks
                )

                # Build citations for the overview
                summary_citations = []
                if chapters_list:
                    for idx, ch in enumerate(chapters_list[:3]):
                        summary_citations.append({
                            "citationId": f"cite_ch_{idx+1}",
                            "documentId": str(document_id),
                            "documentVersionId": str(document_id),
                            "sourceTitle": doc_title,
                            "pageStart": ch.get("pageStart", 1),
                            "pageEnd": ch.get("pageEnd", ch.get("pageStart", 1)),
                            "heading": [ch.get("title", "")],
                            "excerpt": f"Overview of {ch.get('title', '')}"
                        })
                elif intro_chunks:
                    for c in intro_chunks:
                        summary_citations.append({
                            "citationId": f"cite_{str(c.id)[:8]}",
                            "documentId": str(document_id),
                            "documentVersionId": str(document_id),
                            "sourceTitle": doc_title,
                            "pageStart": c.page_start,
                            "pageEnd": c.page_end,
                            "heading": c.heading_path or [],
                            "excerpt": c.text[:180]
                        })

                summary_prompt = (
                    f"You are the SETU Academic Tutor for a school student.\n"
                    f"The student asked for an overview/summary of their uploaded textbook: '{doc_title}'.\n"
                    f"Provide a clear, inspiring, well-structured summary (under 200 words) in plain language, without a greeting.\n"
                    f"Never write LaTeX, raw asterisks, or awkward symbols.\n"
                    f"Curriculum Outline:\n{chapters_str or 'Curriculum topics'}\n\n"
                    f"Introductory Passages:\n{intro_str or 'Foundational textbook contents'}\n\n"
                    f"Describe the major themes and skills covered in the book so the student understands their learning path.\n"
                    f"Reply in the student's preferred language (language code: {reply_language}).\n"
                    f"Student Question: {question_text}\n"
                )
                llm_answer = await ai_provider.generate_chat(
                    messages=[{"role": "user", "content": summary_prompt}],
                    temperature=0.3,
                    max_tokens=900,
                    require_complete=True,
                )
                if not llm_answer or not str(llm_answer).strip():
                    raise RuntimeError("empty tutor response")

                answer_payload = {
                    "answer": sanitize_prose(llm_answer),
                    "citations": summary_citations,
                    "limitations": None,
                    "answeredAt": datetime.datetime.utcnow().isoformat(),
                }
                doubt.status = "answered"
                doubt.last_error_code = None
                doubt.answer_json = answer_payload
                doubt.answered_at = datetime.datetime.utcnow()
                db.commit()
                db.refresh(doubt)
                return {
                    "id": str(doubt.id),
                    "clientDoubtId": doubt.client_doubt_id,
                    "status": doubt.status,
                    "questionText": doubt.question_text,
                    "answerJson": doubt.answer_json,
                    "alreadyExisted": already_existed,
                }

            # Not a summary request: perform hybrid retrieval scoped to the document
            retrieval = await retrieval_service.hybrid_search(
                db=db,
                query=question_text,
                owner_id=owner_id,
                document_id=document_id,
                top_k=5
            )

            results = retrieval.get("results", [])
            supporting_results = select_supporting_citations(results, question_text)
            evidence_str = "\n".join(
                f"- Page {r['pageStart']}: {(r.get('text') or '')[:1200]}"
                for r in results
            )

            title_by_document = {document_id: doc_title}
            for r in results:
                try:
                    r_doc_id = uuid.UUID(str(r.get("documentVersionId")))
                    if r_doc_id not in title_by_document:
                        d_name = db.query(Document.original_filename).filter(Document.id == r_doc_id).scalar()
                        if d_name:
                            title_by_document[r_doc_id] = d_name
                except (TypeError, ValueError):
                    continue

            def _source_title(row: Dict[str, Any]) -> Optional[str]:
                try:
                    return title_by_document.get(uuid.UUID(str(row.get("documentVersionId")))) or doc_title
                except (TypeError, ValueError):
                    return doc_title

            citations = [
                {
                    "citationId": r["citationId"],
                    "documentId": r.get("documentVersionId"),
                    "documentVersionId": r.get("documentVersionId"),
                    "sourceTitle": _source_title(r),
                    "pageStart": r["pageStart"],
                    "pageEnd": r["pageEnd"],
                    "heading": r.get("headingPath", []),
                    "excerpt": (r.get("text") or "")[:180]
                }
                for r in supporting_results
            ]

            # The tutor always answers: grounded when the book supports the
            # question, labeled general knowledge when it does not.
            if retrieval.get("insufficient_evidence") or not results:
                prompt = (
                    "You are the SETU Academic Tutor for a school student.\n"
                    "Answer in at most 130 words, in plain language, without a greeting.\n"
                    "Never write LaTeX, raw backslashes, or strange formatting.\n"
                    f"The student is studying '{doc_title}'. This specific question is not directly covered in the textbook excerpts, "
                    f"so explain the answer accurately from your academic knowledge and mention that this extends beyond the current textbook passages.\n"
                    "Never invent an inaccurate page reference.\n"
                    f"Reply in the student's preferred language (language code: {reply_language}).\n"
                    f"Student Question: {question_text}\n"
                )
                llm_answer = await ai_provider.generate_chat(
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.3,
                    max_tokens=900,
                    require_complete=True,
                )
                if not llm_answer or not str(llm_answer).strip():
                    raise RuntimeError("empty tutor response")
                answer_payload = {
                    "answer": sanitize_prose(llm_answer),
                    "citations": [],
                    "limitations": "general_knowledge",
                    "answeredAt": datetime.datetime.utcnow().isoformat()
                }
            else:
                prompt = (
                    f"You are the SETU Academic Tutor for a school student.\n"
                    f"Answer in at most 140 words, in plain language, without a greeting.\n"
                    f"Never write LaTeX or raw formatting; write numbers and units in plain text.\n"
                    f"Explain clearly and directly using the source evidence below from '{doc_title}'. "
                    f"When the evidence does not contain the answer, say so briefly and explain from your knowledge.\n"
                    f"Reply in the student's preferred language (language code: {reply_language}).\n"
                    f"Student Question: {question_text}\n"
                    f"Source Evidence from the Uploaded Document:\n{evidence_str}\n"
                )
                llm_answer = await ai_provider.generate_chat(
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.2,
                    max_tokens=1400,
                    require_complete=True,
                )
                if not llm_answer or not str(llm_answer).strip():
                    raise RuntimeError("empty tutor response")
                answer_payload = {
                    "answer": sanitize_prose(llm_answer),
                    "citations": citations,
                    "limitations": None,
                    "answeredAt": datetime.datetime.utcnow().isoformat()
                }

            doubt.status = "answered"
            doubt.last_error_code = None
            doubt.answer_json = answer_payload
            doubt.answered_at = datetime.datetime.utcnow()
            db.commit()
            db.refresh(doubt)
        except Exception as e:
            logger.exception(f"Error resolving doubt {client_doubt_id}: {e}")
            try:
                db.rollback()
            except Exception:
                pass
            try:
                doubt_rec = db.query(Doubt).filter(Doubt.id == doubt.id).first()
                if doubt_rec:
                    doubt_rec.status = "needs_retry"
                    doubt_rec.last_error_code = "tutor_unavailable"
                    doubt_rec.answer_json = {
                        "answer": None,
                        "citations": [],
                        "limitations": "tutor_unavailable",
                        "retryable": True,
                        "message": "The tutor is temporarily unavailable. Your question is saved; retry in a moment."
                    }
                    doubt_rec.answered_at = None
                    db.commit()
                    db.refresh(doubt_rec)
                    doubt = doubt_rec
            except Exception as save_err:
                logger.warning(f"Could not persist fallback doubt state: {save_err}")

        return {
            "id": str(doubt.id),
            "clientDoubtId": doubt.client_doubt_id,
            "status": doubt.status,
            "questionText": doubt.question_text,
            "answerJson": doubt.answer_json,
            "alreadyExisted": already_existed
        }


sync_service = SyncService()
