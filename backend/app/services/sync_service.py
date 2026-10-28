import uuid
import datetime
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from app.models.doubts import Doubt, SyncEvent
from app.models.learning import QuizAttempt, ConceptEvidence
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
        Idempotent doubt intake: if client_doubt_id exists for owner, returns it.
        Otherwise generates source-grounded answer with citations.
        """
        # 1. Check existing record
        existing = db.query(Doubt).filter(
            Doubt.owner_id == owner_id,
            Doubt.client_doubt_id == client_doubt_id
        ).first()

        if existing:
            return {
                "id": str(existing.id),
                "clientDoubtId": existing.client_doubt_id,
                "status": existing.status,
                "questionText": existing.question_text,
                "answerJson": existing.answer_json,
                "alreadyExisted": True
            }

        # 2. Retrieve relevant evidence
        retrieval = await retrieval_service.hybrid_search(
            db=db,
            query=question_text,
            owner_id=owner_id,
            top_k=3
        )

        results = retrieval.get("results", [])
        evidence_str = "\n".join([f"- Page {r['pageStart']}: {r['text'][:350]}" for r in results])
        citations = [
            {
                "citationId": r["citationId"],
                "pageStart": r["pageStart"],
                "pageEnd": r["pageEnd"],
                "heading": r.get("headingPath", []),
                "excerpt": r["text"][:180]
            }
            for r in results
        ]

        now_utc = datetime.datetime.now(datetime.timezone.utc)
        if retrieval.get("insufficient_evidence") or not results:
            answer_payload = {
                "answer": "The selected document does not contain sufficient verified evidence to answer this question accurately. Please review the relevant textbook chapter or consult your teacher.",
                "citations": [],
                "limitations": "insufficient_source_evidence",
                "answeredAt": now_utc.isoformat()
            }
            status_val = "answered"
        else:
            prompt = (
                f"You are SETU Academic Tutor.\n"
                f"Answer the student's doubt strictly using only the provided textbook evidence.\n"
                f"Student Question: {question_text}\n"
                f"Verified Textbook Evidence:\n{evidence_str}\n\n"
                f"Provide a clear, age-appropriate, encouraging explanation referencing the exact textbook concepts."
            )
            try:
                llm_answer = await ai_provider.generate_chat(
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.2,
                    max_tokens=600
                )
                answer_payload = {
                    "answer": llm_answer,
                    "citations": citations,
                    "limitations": None,
                    "answeredAt": now_utc.isoformat()
                }
                status_val = "answered"
            except Exception as e:
                # If provider is currently unreachable, mark as queued with retry
                answer_payload = None
                status_val = "needs_retry"

        doubt = Doubt(
            owner_id=owner_id,
            client_doubt_id=client_doubt_id,
            path_id=path_id,
            lesson_version_id=lesson_version_id,
            block_id=block_id,
            source_page=source_page,
            question_text=question_text,
            status=status_val,
            answer_json=answer_payload,
            submitted_at=now_utc,
            answered_at=now_utc if status_val == "answered" else None
        )
        db.add(doubt)
        db.commit()
        db.refresh(doubt)

        return {
            "id": str(doubt.id),
            "clientDoubtId": doubt.client_doubt_id,
            "status": doubt.status,
            "questionText": doubt.question_text,
            "answerJson": doubt.answer_json,
            "alreadyExisted": False
        }

    def sync_batch_events(
        self,
        db: Session,
        owner_id: uuid.UUID,
        events: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Processes batch client sync events with idempotency.
        """
        results = []
        for ev in events:
            client_event_id = ev.get("clientEventId")
            event_type = ev.get("eventType")
            payload = ev.get("payload", {})

            existing = db.query(SyncEvent).filter(
                SyncEvent.owner_id == owner_id,
                SyncEvent.client_event_id == client_event_id
            ).first()

            if existing:
                results.append({
                    "clientEventId": client_event_id,
                    "status": "already_applied",
                    "result": existing.result_json
                })
                continue

            result_data = {"applied": True, "type": event_type}
            sync_rec = SyncEvent(
                owner_id=owner_id,
                client_event_id=client_event_id,
                event_type=event_type,
                payload_json=payload,
                result_json=result_data
            )
            db.add(sync_rec)
            results.append({
                "clientEventId": client_event_id,
                "status": "applied",
                "result": result_data
            })

        db.commit()
        return results

sync_service = SyncService()
