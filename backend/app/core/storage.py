import json
import os
import re
from urllib.parse import quote

import httpx
from typing import Optional
from app.core.config import settings


_BUCKET_RE = re.compile(r"^[A-Za-z0-9._-]+$")


class StorageService:
    """Private object storage with an explicit, test-only local backend."""

    def __init__(self):
        base = settings.SUPABASE_URL
        if base and not base.startswith("http"):
            base = f"https://{base}"
        self.base_url = base.rstrip("/") if base else ""
        self.secret_key = settings.SUPABASE_SECRET_KEY
        self.backend = (settings.STORAGE_BACKEND or "supabase").strip().lower()
        self.local_root = os.path.realpath(os.path.abspath(settings.LOCAL_STORAGE_DIR))
        if self.backend == "local" and settings.APP_ENV not in ("local", "test"):
            raise RuntimeError(
                "Local storage is only allowed when APP_ENV is local or test. "
                "Configure Supabase storage for this deployment."
            )

    def _headers(self, content_type: Optional[str] = None) -> dict:
        h = {
            "apikey": self.secret_key,
            "Authorization": f"Bearer {self.secret_key}"
        }
        if content_type:
            h["Content-Type"] = content_type
        return h

    def _object_path(self, bucket: str, path: str) -> str:
        encoded = "/".join(quote(part, safe="") for part in path.split("/"))
        return f"{self.base_url}/storage/v1/object/{bucket}/{encoded}"

    def _local_path(self, bucket: str, path: str) -> str:
        if not _BUCKET_RE.fullmatch(bucket or ""):
            raise ValueError("Invalid storage bucket name.")
        normalised = (path or "").replace("\\", "/")
        parts = normalised.split("/")
        if not normalised or any(part in ("", ".", "..") for part in parts):
            raise ValueError("Invalid storage object path.")
        target = os.path.realpath(os.path.join(self.local_root, bucket, *parts))
        if os.path.commonpath([self.local_root, target]) != self.local_root:
            raise ValueError("Storage object path escapes the storage root.")
        return target

    async def upload_file(self, bucket: str, path: str, content: bytes, mime_type: str = "application/octet-stream") -> bool:
        if self.backend == "local":
            target = self._local_path(bucket, path)
            os.makedirs(os.path.dirname(target), exist_ok=True)
            with open(target, "wb") as handle:
                handle.write(content)
            return True
        if not self.base_url or not self.secret_key:
            return False
        url = self._object_path(bucket, path)
        headers = self._headers(mime_type)
        headers["x-upsert"] = "true"
        timeout = 180.0
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(url, content=content, headers=headers)
            return resp.status_code in (200, 201)

    async def download_file(self, bucket: str, path: str) -> Optional[bytes]:
        if self.backend == "local":
            target = self._local_path(bucket, path)
            if not os.path.isfile(target):
                return None
            with open(target, "rb") as handle:
                return handle.read()
        if not self.base_url or not self.secret_key:
            return None
        encoded = "/".join(quote(part, safe="") for part in path.split("/"))
        url = f"{self.base_url}/storage/v1/object/authenticated/{bucket}/{encoded}"
        async with httpx.AsyncClient(timeout=180.0) as client:
            resp = await client.get(url, headers=self._headers())
            if resp.status_code == 200:
                return resp.content
            return None

    async def delete_file(self, bucket: str, path: str) -> bool:
        if self.backend == "local":
            target = self._local_path(bucket, path)
            try:
                os.remove(target)
                return True
            except FileNotFoundError:
                return False
        if not self.base_url or not self.secret_key:
            return False
        url = f"{self.base_url}/storage/v1/object/{bucket}"
        headers = self._headers("application/json")
        payload = {"prefixes": [path]}
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.request("DELETE", url, content=json.dumps(payload), headers=headers)
            return resp.status_code == 200

    async def check_health(self) -> bool:
        if self.backend == "local":
            try:
                os.makedirs(self.local_root, exist_ok=True)
                probe = os.path.join(self.local_root, ".setu-write-probe")
                with open(probe, "w", encoding="utf-8") as handle:
                    handle.write("ok")
                os.remove(probe)
                return True
            except OSError:
                return False
        if not self.base_url or not self.secret_key:
            return False
        try:
            url = f"{self.base_url}/storage/v1/bucket"
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(url, headers=self._headers())
                return resp.status_code == 200
        except Exception:
            return False


storage_service = StorageService()
