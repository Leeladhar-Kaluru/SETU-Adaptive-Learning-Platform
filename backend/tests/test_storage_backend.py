import pytest

from app.core import storage as storage_module
from app.core.storage import StorageService


def _local_service(tmp_path, monkeypatch) -> StorageService:
    monkeypatch.setattr(storage_module.settings, "STORAGE_BACKEND", "local")
    monkeypatch.setattr(storage_module.settings, "LOCAL_STORAGE_DIR", str(tmp_path))
    monkeypatch.setattr(storage_module.settings, "APP_ENV", "test")
    return StorageService()


@pytest.mark.asyncio
async def test_local_storage_round_trip(tmp_path, monkeypatch):
    service = _local_service(tmp_path, monkeypatch)
    key = "documents/owner/file.txt"

    assert await service.upload_file("setu-documents", key, b"chapter text", "text/plain")
    assert await service.download_file("setu-documents", key) == b"chapter text"
    assert await service.check_health() is True
    assert await service.delete_file("setu-documents", key) is True
    assert await service.download_file("setu-documents", key) is None


@pytest.mark.asyncio
async def test_local_storage_rejects_path_traversal(tmp_path, monkeypatch):
    service = _local_service(tmp_path, monkeypatch)

    with pytest.raises(ValueError):
        await service.upload_file("setu-documents", "../escape.txt", b"x")
    with pytest.raises(ValueError):
        await service.upload_file("setu-documents", "documents/..\\..\\escape.txt", b"x")
    with pytest.raises(ValueError):
        await service.upload_file("../bucket", "documents/file.txt", b"x")


def test_local_storage_is_refused_outside_local_and_test(monkeypatch):
    monkeypatch.setattr(storage_module.settings, "STORAGE_BACKEND", "local")
    monkeypatch.setattr(storage_module.settings, "APP_ENV", "production")

    with pytest.raises(RuntimeError):
        StorageService()
