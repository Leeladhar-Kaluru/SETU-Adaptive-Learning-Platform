import uuid
import pytest

from app.models.documents import Document, DocumentChunk
from app.services import retrieval as retrieval_module
from app.services.retrieval import retrieval_service


@pytest.mark.asyncio
async def test_retrieval_excludes_unembedded_and_foreign_chunks(db, monkeypatch):
    owner_id = uuid.uuid4()
    other_id = uuid.uuid4()
    doc = Document(
        owner_id=owner_id, original_filename="cells.pdf", storage_key="documents/cells.pdf",
        mime_type="application/pdf", size_bytes=10, status="ready", page_count=1,
    )
    foreign = Document(
        owner_id=other_id, original_filename="foreign.pdf", storage_key="documents/foreign.pdf",
        mime_type="application/pdf", size_bytes=10, status="ready", page_count=1,
    )
    db.add_all([doc, foreign])
    db.flush()
    vector = [1.0] + [0.0] * 767
    db.add_all([
        DocumentChunk(
            document_id=doc.id, page_start=1, page_end=1, chunk_index=0,
            heading_path=[], text="cells and membranes", text_hash="h1",
            embedding=vector, embedding_model_id="text-embedding-nomic-embed-text-v1.5",
            embedding_dimension=768,
        ),
        DocumentChunk(
            document_id=doc.id, page_start=1, page_end=1, chunk_index=1,
            heading_path=[], text="cells without embedding", text_hash="h2",
            embedding=None,
        ),
        DocumentChunk(
            document_id=foreign.id, page_start=1, page_end=1, chunk_index=0,
            heading_path=[], text="foreign cells", text_hash="h3", embedding=vector,
            embedding_model_id="text-embedding-nomic-embed-text-v1.5",
            embedding_dimension=768,
        ),
    ])
    db.commit()

    async def fake_query_embedding(text):
        return vector

    monkeypatch.setattr(retrieval_module.ai_provider, "get_embedding", fake_query_embedding)
    result = await retrieval_service.hybrid_search(db, "cells", owner_id=owner_id, top_k=5)
    texts = [item["text"] for item in result["results"]]
    assert "cells and membranes" in texts
    assert "cells without embedding" not in texts
    assert "foreign cells" not in texts
