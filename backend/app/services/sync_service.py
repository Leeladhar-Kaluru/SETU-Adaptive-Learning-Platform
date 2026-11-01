import re
import uuid
import datetime
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from app.models.documents import Document
from app.models.doubts import Doubt
from app.models.learning import LearningPath
from app.models.profiles import UserProfile
from app.services.retrieval import retrieval_service
from app.core.ai_provider import ai_provider

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
            # Scope grounding to the document behind the lesson the student is
            # reading. A question without a lesson context has no book attached,
            # so it takes the labeled general-knowledge path instead of pulling
            # weak citations from an unrelated book in the library.
            document_id = None
            if path_id:
                path = db.query(LearningPath).filter(
                    LearningPath.id == path_id,
                    LearningPath.owner_id == owner_id,
                ).first()
                if path and path.document_id:
                    document_id = path.document_id

            reply_language = _student_language(db, owner_id)

            if not path_id or not document_id:
                # Hybrid chat: without a book attached to this question the
                # tutor still helps, but the answer is general knowledge and is
                # always labeled as such — never presented as page-grounded.
                general_prompt = (
                    "You are the SETU Academic Tutor for a school student.\n"
                    "Answer in at most 120 words, in plain language, without a greeting.\n"
                    "Never write LaTeX or markdown; write numbers like 82°30′ E in plain text.\n"
                    "The student has not attached any book, so answer from general "
                    "knowledge and never invent a page reference or citation.\n"
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
                    "answer": llm_answer,
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

            retrieval = await retrieval_service.hybrid_search(
                db=db,
                query=question_text,
                owner_id=owner_id,
                document_id=document_id,
                top_k=3
            )

            results = retrieval.get("results", [])
            supporting_results = select_supporting_citations(results, question_text)
            evidence_str = "\n".join(
                f"- Page {r['pageStart']}: {(r.get('text') or '')[:1200]}"
                for r in results
            )

            title_by_document = {}
            document_ids = set()
            for r in results:
                try:
                    document_ids.add(uuid.UUID(str(r.get("documentVersionId"))))
                except (TypeError, ValueError):
                    continue
            if document_ids:
                title_by_document = {
                    doc_id: name
                    for doc_id, name in db.query(Document.id, Document.original_filename)
                    .filter(Document.id.in_(document_ids), Document.owner_id == owner_id)
                    .all()
                }

            def _source_title(row: Dict[str, Any]) -> Optional[str]:
                try:
                    return title_by_document.get(uuid.UUID(str(row.get("documentVersionId"))))
                except (TypeError, ValueError):
                    return None

            citations = [
                {
                    "citationId": r["citationId"],
                    "documentId": r.get("documentVersionId"),
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
                    "Answer in at most 120 words, in plain language, without a greeting.\n"
                    "Never write LaTeX or markdown; write numbers like 82°30′ E in plain text.\n"
                    "The student's book does not mention this, so answer from your own "
                    "knowledge and say plainly that the book does not cover it.\n"
                    "Never invent a page reference or citation.\n"
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
                    "answer": llm_answer,
                    "citations": [],
                    "limitations": "general_knowledge",
                    "answeredAt": datetime.datetime.utcnow().isoformat()
                }
            else:
                prompt = (
                    f"You are the SETU Academic Tutor for a school student.\n"
                    f"Answer in at most 120 words, in plain language, without a greeting.\n"
                    f"Never write LaTeX or markdown; write numbers like 82°30′ E in plain text.\n"
                    f"Prefer the source evidence below. When the evidence does not contain the "
                    f"answer, say so in one sentence and then answer from your own knowledge.\n"
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
                    "answer": llm_answer,
                    "citations": citations,
                    "limitations": None,
                    "answeredAt": datetime.datetime.utcnow().isoformat()
                }

            doubt.status = "answered"
            doubt.last_error_code = None
            doubt.answer_json = answer_payload
            doubt.answered_at = datetime.datetime.utcnow()
        except Exception:
            # Never leak provider internals to the student. Persist a truthful
            # retryable state so the same client_doubt_id can be retried.
            doubt.status = "needs_retry"
            doubt.last_error_code = "tutor_unavailable"
            doubt.answer_json = {
                "answer": None,
                "citations": [],
                "limitations": "tutor_unavailable",
                "retryable": True,
                "message": "The tutor is unavailable. Your question is saved; retry in a moment."
            }
            doubt.answered_at = None

        db.commit()
        db.refresh(doubt)

        return {
            "id": str(doubt.id),
            "clientDoubtId": doubt.client_doubt_id,
            "status": doubt.status,
            "questionText": doubt.question_text,
            "answerJson": doubt.answer_json,
            "alreadyExisted": already_existed
        }


sync_service = SyncService()
