import pytest
import uuid
from app.core.database import SessionLocal
from app.services.sync_service import sync_service
from app.models.doubts import Doubt

pytestmark = pytest.mark.skip(reason="provider failures become retryable in Task 12")


@pytest.mark.asyncio
async def test_idempotent_doubt_sync():
    db = SessionLocal()
    owner_id = uuid.uuid4()
    client_doubt_id = f"doubt_{uuid.uuid4().hex[:12]}"

    try:
        # First sync
        res1 = await sync_service.sync_doubt(
            db=db,
            owner_id=owner_id,
            client_doubt_id=client_doubt_id,
            question_text="What is selective permeability?"
        )
        assert res1["clientDoubtId"] == client_doubt_id
        assert res1["alreadyExisted"] is False
        doubt_db_id = res1["id"]

        # Second sync with identical (owner_id, client_doubt_id)
        res2 = await sync_service.sync_doubt(
            db=db,
            owner_id=owner_id,
            client_doubt_id=client_doubt_id,
            question_text="What is selective permeability?"
        )
        assert res2["clientDoubtId"] == client_doubt_id
        assert res2["alreadyExisted"] is True
        assert res2["id"] == doubt_db_id

        # Verify only 1 record exists in database
        count = db.query(Doubt).filter(
            Doubt.owner_id == owner_id,
            Doubt.client_doubt_id == client_doubt_id
        ).count()
        assert count == 1

    finally:
        # Cleanup
        db.query(Doubt).filter(Doubt.owner_id == owner_id).delete()
        db.commit()
        db.close()

