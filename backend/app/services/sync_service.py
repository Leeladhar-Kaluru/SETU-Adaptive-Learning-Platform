import uuid
import datetime
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session
from app.models.doubts import Doubt
from app.services.retrieval import retrieval_service
from app.core.ai_provider import ai_provider


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
            retrieval = await retrieval_service.hybrid_search(
                db=db,
                query=question_text,
                owner_id=owner_id,
                top_k=3
            )

            results = retrieval.get("results", [])
            evidence_str = "\n".join(
                f"- Page {r['pageStart']}: {(r.get('text') or '')[:350]}"
                for r in results
            )
            citations = [
                {
                    "citationId": r["citationId"],
                    "pageStart": r["pageStart"],
                    "pageEnd": r["pageEnd"],
                    "heading": r.get("headingPath", []),
                    "excerpt": (r.get("text") or "")[:180]
                }
                for r in results
            ]

            if retrieval.get("insufficient_evidence") or not results:
                answer_payload = {
                    "answer": "The selected document does not contain sufficient verified evidence to answer this question accurately. Please review the relevant textbook chapter or consult your teacher.",
                    "citations": [],
                    "limitations": "insufficient_source_evidence",
                    "answeredAt": datetime.datetime.utcnow().isoformat()
                }
            else:
                prompt = (
                    f"You are SETU Academic Tutor.\n"
                    f"Answer the student's doubt strictly using only the provided textbook evidence.\n"
                    f"Student Question: {question_text}\n"
                    f"Verified Textbook Evidence:\n{evidence_str}\n\n"
                    f"Provide a clear, age-appropriate, encouraging explanation referencing the exact textbook concepts."
                )
                llm_answer = await ai_provider.generate_chat(
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.2,
                    max_tokens=600
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
