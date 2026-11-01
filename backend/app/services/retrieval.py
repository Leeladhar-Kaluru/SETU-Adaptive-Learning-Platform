import uuid
from typing import List, Dict, Any, Optional
from sqlalchemy import text
from sqlalchemy.orm import Session
from app.core.ai_provider import ai_provider
from app.core.config import settings

class RetrievalService:
    async def hybrid_search(
        self,
        db: Session,
        query: str,
        owner_id: uuid.UUID,
        document_id: Optional[uuid.UUID] = None,
        top_k: int = 5
    ) -> Dict[str, Any]:
        """
        Executes hybrid retrieval (pgvector 768d + Postgres FTS) with access filtering
        and generates verifiable citation objects.
        """
        if not query.strip():
            return {"results": [], "insufficient_evidence": True, "reason": "Query is empty"}

        # 1. Generate query embedding
        query_vec = await ai_provider.get_embedding(query)
        vec_str = "[" + ",".join(str(x) for x in query_vec) + "]"

        # 2. Access condition and parameters
        if document_id:
            access_condition = """
                d.id = :doc_id
                AND (
                    d.owner_id = :owner_id
                    OR d.id IN (SELECT lp.document_id FROM learning_paths lp WHERE lp.owner_id = :owner_id AND lp.document_id IS NOT NULL)
                    OR d.id IN (
                        SELECT d2.id FROM documents d2
                        JOIN classrooms c ON c.owner_teacher_id = d2.owner_id
                        JOIN classroom_memberships cm ON cm.classroom_id = c.id
                        WHERE cm.student_id = :owner_id
                    )
                    OR d.source_mode IN ('catalog', 'catalogue', 'curriculum', 'sample')
                    OR EXISTS (SELECT 1 FROM user_profiles up WHERE up.id = :owner_id AND up.role IN ('teacher', 'admin'))
                )
            """
        else:
            access_condition = """
                (
                    d.owner_id = :owner_id
                    OR d.id IN (SELECT lp.document_id FROM learning_paths lp WHERE lp.owner_id = :owner_id AND lp.document_id IS NOT NULL)
                    OR d.id IN (
                        SELECT d2.id FROM documents d2
                        JOIN classrooms c ON c.owner_teacher_id = d2.owner_id
                        JOIN classroom_memberships cm ON cm.classroom_id = c.id
                        WHERE cm.student_id = :owner_id
                    )
                    OR d.source_mode IN ('catalog', 'catalogue', 'curriculum', 'sample')
                    OR EXISTS (SELECT 1 FROM user_profiles up WHERE up.id = :owner_id AND up.role IN ('teacher', 'admin'))
                )
            """

        params: Dict[str, Any] = {
            "owner_id": str(owner_id),
            "top_k": top_k * 2,
            "vec_str": vec_str,
            "embedding_model": settings.EMBEDDING_MODEL,
            "embedding_dim": settings.EMBEDDING_DIMENSION,
        }
        if document_id:
            params["doc_id"] = str(document_id)

        vector_sql = f"""
            SELECT c.id, c.document_id, c.page_start, c.page_end, c.heading_path, c.text,
                   (c.embedding <=> cast(:vec_str as vector)) as distance
            FROM document_chunks c
            JOIN documents d ON c.document_id = d.id
            WHERE {access_condition}
              AND d.deleted_at IS NULL
              AND d.status IN ('awaiting_review', 'ready')
              AND c.embedding IS NOT NULL
              AND c.embedding_model_id = :embedding_model
              AND c.embedding_dimension = :embedding_dim
              AND (c.embedding <=> cast(:vec_str as vector)) <= 0.65
            ORDER BY distance ASC
            LIMIT :top_k;
        """
        vec_rows = db.execute(text(vector_sql), params).fetchall()

        # 3. Full-Text Search query
        params["query_text"] = query
        fts_sql = f"""
            SELECT c.id, c.document_id, c.page_start, c.page_end, c.heading_path, c.text,
                   ts_rank_cd(c.search_text, plainto_tsquery('english', :query_text)) as fts_score
            FROM document_chunks c
            JOIN documents d ON c.document_id = d.id
            WHERE {access_condition}
              AND d.deleted_at IS NULL
              AND d.status IN ('awaiting_review', 'ready')
              AND c.embedding IS NOT NULL
              AND c.embedding_model_id = :embedding_model
              AND c.embedding_dimension = :embedding_dim
              AND c.search_text @@ plainto_tsquery('english', :query_text)
            ORDER BY fts_score DESC
            LIMIT :top_k;
        """
        fts_rows = db.execute(text(fts_sql), params).fetchall()

        # 4. Reciprocal Rank Fusion (RRF)
        scores: Dict[str, float] = {}
        chunk_map: Dict[str, Any] = {}

        for rank, row in enumerate(vec_rows):
            cid = str(row[0])
            scores[cid] = scores.get(cid, 0.0) + (1.0 / (60.0 + rank + 1))
            chunk_map[cid] = row

        for rank, row in enumerate(fts_rows):
            cid = str(row[0])
            scores[cid] = scores.get(cid, 0.0) + (1.0 / (60.0 + rank + 1))
            chunk_map[cid] = row

        # Sort chunks by fused score
        sorted_cids = sorted(scores.keys(), key=lambda k: scores[k], reverse=True)[:top_k]

        results = []
        for cid in sorted_cids:
            row = chunk_map[cid]
            doc_id = str(row[1])
            page_start = row[2]
            page_end = row[3]
            heading = row[4]
            chunk_text = row[5]

            results.append({
                "citationId": f"cite_{cid[:8]}",
                "chunkId": cid,
                "documentVersionId": doc_id,
                "pageStart": page_start,
                "pageEnd": page_end,
                "headingPath": heading if heading else [],
                "text": chunk_text,
                "score": scores[cid]
            })

        # Check if evidence is sufficient
        insufficient = (len(results) == 0 or (len(results) > 0 and scores[sorted_cids[0]] < 0.01))

        return {
            "results": results,
            "insufficient_evidence": insufficient,
            "reason": "Insufficient source passage matches for grounding" if insufficient else None
        }

retrieval_service = RetrievalService()

