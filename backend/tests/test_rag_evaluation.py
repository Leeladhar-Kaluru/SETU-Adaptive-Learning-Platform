import pytest
import uuid
import hashlib
from sqlalchemy import text
from app.core.database import SessionLocal
from app.models.documents import Document, DocumentChunk
from app.services.retrieval import retrieval_service
from app.services.sync_service import sync_service

pytestmark = pytest.mark.integration


@pytest.fixture
def rag_eval_fixture():
    db = SessionLocal()
    owner_a = uuid.uuid4()
    owner_b = uuid.uuid4()

    # Create document for Owner A: Class 9 Biology - Cell Membrane
    doc_a = Document(
        id=uuid.uuid4(),
        owner_id=owner_a,
        original_filename="NCERT Class 9 Science Chapter 5 - The Fundamental Unit of Life.pdf",
        storage_bucket="setu-documents",
        storage_key=f"{owner_a}/eval_cell.pdf",
        mime_type="application/pdf",
        size_bytes=1024 * 50,
        sha256="sha256_mock_eval_a",
        status="ready",
        page_count=4
    )
    db.add(doc_a)
    db.commit()

    text_1 = "The plasma membrane is the outermost covering of the cell that separates the contents of the cell from its external environment. The plasma membrane permits or allows the entry and exit of some materials in and out of the cell. Therefore, the cell membrane is called a selectively permeable membrane."
    text_2 = "Some substances like carbon dioxide or oxygen can move across the cell membrane by a process called diffusion. Diffusion is the spontaneous movement of a substance from a region of high concentration to a region where its concentration is low. Water also obeys the law of diffusion across a selectively permeable membrane, which is called osmosis."

    chunk_1 = DocumentChunk(
        id=uuid.uuid4(),
        document_id=doc_a.id,
        chunk_index=0,
        page_start=59,
        page_end=59,
        heading_path=["Chapter 5", "5.2.1 Plasma Membrane or Cell Membrane"],
        text=text_1,
        text_hash=hashlib.sha256(text_1.encode()).hexdigest()
    )
    chunk_2 = DocumentChunk(
        id=uuid.uuid4(),
        document_id=doc_a.id,
        chunk_index=1,
        page_start=60,
        page_end=60,
        heading_path=["Chapter 5", "5.2.1 Diffusion and Osmosis"],
        text=text_2,
        text_hash=hashlib.sha256(text_2.encode()).hexdigest()
    )
    db.add_all([chunk_1, chunk_2])
    db.commit()

    # Embeddings for Document A
    from app.core.ai_provider import ai_provider
    import asyncio

    async def embed_chunks():
        vec1 = await ai_provider.get_embedding(chunk_1.text)
        vec2 = await ai_provider.get_embedding(chunk_2.text)
        db.execute(text("UPDATE document_chunks SET embedding = :emb WHERE id = :id"),
                   {"emb": "[" + ",".join(str(x) for x in vec1) + "]", "id": str(chunk_1.id)})
        db.execute(text("UPDATE document_chunks SET embedding = :emb WHERE id = :id"),
                   {"emb": "[" + ",".join(str(x) for x in vec2) + "]", "id": str(chunk_2.id)})
        db.commit()

    asyncio.run(embed_chunks())

    # Create private Document for Owner B (Distractor & Access control test)
    doc_b = Document(
        id=uuid.uuid4(),
        owner_id=owner_b,
        original_filename="Owner B Private Math Document.pdf",
        storage_bucket="setu-documents",
        storage_key=f"{owner_b}/eval_math.pdf",
        mime_type="application/pdf",
        size_bytes=1024 * 20,
        sha256="sha256_mock_eval_b",
        status="ready",
        page_count=2
    )
    db.add(doc_b)
    db.commit()

    text_b = "A linear equation in one variable is an equation which can be written in the form ax + b = 0 where a and b are real numbers and a is not equal to zero."
    chunk_b = DocumentChunk(
        id=uuid.uuid4(),
        document_id=doc_b.id,
        chunk_index=0,
        page_start=12,
        page_end=12,
        heading_path=["Chapter 2", "Linear Equations"],
        text=text_b,
        text_hash=hashlib.sha256(text_b.encode()).hexdigest()
    )
    db.add(chunk_b)
    db.commit()

    async def embed_chunk_b():
        vec_b = await ai_provider.get_embedding(chunk_b.text)
        db.execute(text("UPDATE document_chunks SET embedding = :emb WHERE id = :id"),
                   {"emb": "[" + ",".join(str(x) for x in vec_b) + "]", "id": str(chunk_b.id)})
        db.commit()

    asyncio.run(embed_chunk_b())

    yield {
        "db": db,
        "owner_a": owner_a,
        "owner_b": owner_b,
        "doc_a": doc_a,
        "doc_b": doc_b,
        "chunk_1": chunk_1,
        "chunk_2": chunk_2,
        "chunk_b": chunk_b
    }

    # Cleanup
    try:
        db.execute(text("DELETE FROM document_chunks WHERE document_id IN (:da, :db)"),
                   {"da": str(doc_a.id), "db": str(doc_b.id)})
        db.execute(text("DELETE FROM documents WHERE id IN (:da, :db)"),
                   {"da": str(doc_a.id), "db": str(doc_b.id)})
        db.commit()
    except Exception:
        db.rollback()
    finally:
        db.close()


@pytest.mark.asyncio
async def test_rag_paraphrase_retrieval(rag_eval_fixture):
    """
    Tests semantic retrieval for paraphrased questions with varied phrasing.
    """
    db = rag_eval_fixture["db"]
    owner_a = rag_eval_fixture["owner_a"]

    # Paraphrase 1: "Why is the cell membrane called selectively permeable?"
    res1 = await retrieval_service.hybrid_search(
        db=db,
        query="Why is the cell membrane called selectively permeable?",
        owner_id=owner_a,
        top_k=2
    )
    assert not res1.get("insufficient_evidence")
    assert len(res1["results"]) > 0
    top_chunk = res1["results"][0]
    assert top_chunk["pageStart"] == 59
    assert "selectively permeable" in top_chunk["text"]

    # Paraphrase 2: "How do oxygen and carbon dioxide move across cell boundaries?"
    res2 = await retrieval_service.hybrid_search(
        db=db,
        query="How do oxygen and carbon dioxide move across cell boundaries?",
        owner_id=owner_a,
        top_k=2
    )
    assert not res2.get("insufficient_evidence")
    assert len(res2["results"]) > 0
    top_chunk2 = res2["results"][0]
    assert top_chunk2["pageStart"] == 60
    assert "diffusion" in top_chunk2["text"].lower()


@pytest.mark.asyncio
async def test_rag_multilingual_query(rag_eval_fixture):
    """
    Tests query with Indian school multilingual phrasing (e.g. Hinglish / transliterated terminology).
    """
    db = rag_eval_fixture["db"]
    owner_a = rag_eval_fixture["owner_a"]

    res = await retrieval_service.hybrid_search(
        db=db,
        query="cell membrane diffusion aur osmosis process kya hai",
        owner_id=owner_a,
        top_k=2
    )
    assert not res.get("insufficient_evidence")
    assert len(res["results"]) > 0
    # Should resolve to the diffusion/osmosis page (page 60)
    pages = [r["pageStart"] for r in res["results"]]
    assert 60 in pages


@pytest.mark.asyncio
async def test_rag_private_document_isolation(rag_eval_fixture):
    """
    Verifies that Owner A cannot retrieve Owner B's document, and Owner B cannot retrieve Owner A's.
    """
    db = rag_eval_fixture["db"]
    owner_a = rag_eval_fixture["owner_a"]
    owner_b = rag_eval_fixture["owner_b"]

    # Owner A searches for math linear equation (exists only in Owner B's doc)
    res_a = await retrieval_service.hybrid_search(
        db=db,
        query="linear equation in one variable ax + b = 0",
        owner_id=owner_a,
        top_k=5
    )
    # Must abstain or return empty for Owner A
    assert len(res_a["results"]) == 0
    assert res_a.get("insufficient_evidence") is True

    # Owner B searching for it succeeds
    res_b = await retrieval_service.hybrid_search(
        db=db,
        query="linear equation in one variable ax + b = 0",
        owner_id=owner_b,
        top_k=5
    )
    assert len(res_b["results"]) > 0
    assert res_b["results"][0]["pageStart"] == 12


@pytest.mark.asyncio
async def test_rag_out_of_domain_abstention(rag_eval_fixture):
    """
    Verifies honest abstention when question has no grounding in user's documents.
    """
    db = rag_eval_fixture["db"]
    owner_a = rag_eval_fixture["owner_a"]

    # Completely unrelated question
    res = await retrieval_service.hybrid_search(
        db=db,
        query="What is the capital city of Australia and its currency?",
        owner_id=owner_a,
        top_k=3
    )
    assert res.get("insufficient_evidence") is True

    # Empty string query
    res_empty = await retrieval_service.hybrid_search(
        db=db,
        query="",
        owner_id=owner_a,
        top_k=3
    )
    assert res_empty.get("insufficient_evidence") is True
    assert res_empty["results"] == []


@pytest.mark.asyncio
async def test_rag_grounded_answer_and_citation_contract(rag_eval_fixture):
    """
    Verifies that doubt answering produces explicit page citations and refusal when ungrounded.
    """
    db = rag_eval_fixture["db"]
    owner_a = rag_eval_fixture["owner_a"]

    # 1. Grounded doubt
    client_doubt_id = f"eval-doubt-{uuid.uuid4().hex[:8]}"
    doubt_res = await sync_service.sync_doubt(
        db=db,
        owner_id=owner_a,
        client_doubt_id=client_doubt_id,
        question_text="What is osmosis and does it require a selectively permeable membrane?"
    )
    assert doubt_res["status"] == "answered"
    answer_json = doubt_res["answerJson"]
    assert "citations" in answer_json
    citations = answer_json["citations"]
    assert len(citations) > 0
    # Citation must contain page number and heading
    assert any(c["pageStart"] == 60 for c in citations)

    # 2. Out-of-domain doubt (must refuse without hallucinating citations)
    client_doubt_ood = f"eval-doubt-ood-{uuid.uuid4().hex[:8]}"
    doubt_ood = await sync_service.sync_doubt(
        db=db,
        owner_id=owner_a,
        client_doubt_id=client_doubt_ood,
        question_text="How many moons does Jupiter have?"
    )
    assert doubt_ood["status"] == "answered"
    ood_answer = doubt_ood["answerJson"]
    assert ood_answer["citations"] == []
    assert ood_answer.get("limitations") == "insufficient_source_evidence"
    assert "does not contain enough evidence" in ood_answer["answer"]
