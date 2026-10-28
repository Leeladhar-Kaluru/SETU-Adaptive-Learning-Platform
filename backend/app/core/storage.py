import json
import httpx
from typing import Optional
from app.core.config import settings

class StorageService:
    def __init__(self):
        base = settings.SUPABASE_URL
        if base and not base.startswith("http"):
            base = f"https://{base}"
        self.base_url = base.rstrip("/") if base else ""
        self.secret_key = settings.SUPABASE_SECRET_KEY

    def _headers(self, content_type: Optional[str] = None) -> dict:
        h = {
            "apikey": self.secret_key,
            "Authorization": f"Bearer {self.secret_key}"
        }
        if content_type:
            h["Content-Type"] = content_type
        return h

    async def upload_file(self, bucket: str, path: str, content: bytes, mime_type: str = "application/octet-stream") -> bool:
        if not self.base_url or not self.secret_key:
            return False
        url = f"{self.base_url}/storage/v1/object/{bucket}/{path}"
        headers = self._headers(mime_type)
        headers["x-upsert"] = "true"
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(url, content=content, headers=headers)
            return resp.status_code in (200, 201)

    async def download_file(self, bucket: str, path: str) -> Optional[bytes]:
        if not self.base_url or not self.secret_key:
            return None
        url = f"{self.base_url}/storage/v1/object/authenticated/{bucket}/{path}"
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(url, headers=self._headers())
            if resp.status_code == 200:
                return resp.content
            return None

    async def delete_file(self, bucket: str, path: str) -> bool:
        if not self.base_url or not self.secret_key:
            return False
        url = f"{self.base_url}/storage/v1/object/{bucket}"
        headers = self._headers("application/json")
        payload = {"prefixes": [path]}
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.request("DELETE", url, content=json.dumps(payload), headers=headers)
            return resp.status_code == 200

    async def check_health(self) -> bool:
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
