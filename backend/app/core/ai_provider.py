import json
import httpx
from typing import List, Dict, Any, Optional
from app.core.config import settings


class EmbeddingUnavailableError(RuntimeError):
    """The configured embedding provider could not produce valid vectors."""


class AIProviderService:
    def __init__(self):
        self.base_url = settings.LLM_BASE_URL.rstrip("/")
        self.chat_model = settings.LLM_MODEL
        self.embed_model = settings.EMBEDDING_MODEL
        self.expected_dim = settings.EMBEDDING_DIMENSION

    async def check_health(self) -> Dict[str, Any]:
        """Probes the configured provider endpoint for models and embeddings."""
        status = {
            "provider_url": self.base_url,
            "chat_model": self.chat_model,
            "embed_model": self.embed_model,
            "chat_ready": False,
            "embed_ready": False,
            "probed_dimension": None,
            "dimension_match": False,
            "error": None
        }
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                # 1. Probe models
                models_resp = await client.get(f"{self.base_url}/models")
                if models_resp.status_code == 200:
                    status["chat_ready"] = True
                
                # 2. Probe embedding dimension
                embed_payload = {"model": self.embed_model, "input": "health probe"}
                embed_resp = await client.post(f"{self.base_url}/embeddings", json=embed_payload)
                if embed_resp.status_code == 200:
                    data = embed_resp.json()
                    vec = data["data"][0]["embedding"]
                    dim = len(vec)
                    status["embed_ready"] = True
                    status["probed_dimension"] = dim
                    status["dimension_match"] = (dim == self.expected_dim)
        except Exception as e:
            status["error"] = str(e)

        return status

    async def get_embedding(self, text: str) -> List[float]:
        vectors = await self.get_embeddings_batch([text])
        return vectors[0]

    async def get_embeddings_batch(self, texts: List[str]) -> List[List[float]]:
        if not texts:
            return []
        clean_inputs = [text.strip() for text in texts]
        if any(not text for text in clean_inputs):
            raise ValueError("Cannot embed empty text; remove blank chunks before embedding.")

        url = f"{self.base_url}/embeddings"
        payload = {"model": self.embed_model, "input": clean_inputs}
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(url, json=payload)
        except Exception as exc:
            raise EmbeddingUnavailableError("Embedding provider is unreachable.") from exc

        if response.status_code != 200:
            raise EmbeddingUnavailableError(
                f"Embedding provider returned status {response.status_code}."
            )

        data = response.json()
        items = sorted(data.get("data", []), key=lambda item: item.get("index", 0))
        if len(items) != len(clean_inputs):
            raise ValueError(
                f"Embedding count mismatch: requested {len(clean_inputs)}, received {len(items)}."
            )

        vectors = [item.get("embedding") or [] for item in items]
        for vector in vectors:
            if len(vector) != self.expected_dim:
                raise ValueError(
                    f"Embedding dimension mismatch: expected {self.expected_dim}, got {len(vector)}."
                )
        return vectors

    async def generate_chat(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.2,
        max_tokens: int = 1500,
        response_format: Optional[Dict[str, str]] = None
    ) -> str:
        """Sends chat completion request to the configured local or hosted LLM."""
        url = f"{self.base_url}/chat/completions"
        payload: Dict[str, Any] = {
            "model": self.chat_model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens
        }
        if response_format:
            payload["response_format"] = response_format

        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(url, json=payload)
            if resp.status_code != 200:
                raise RuntimeError(f"LLM chat completion failed with status {resp.status_code}: {resp.text}")

            data = resp.json()
            message = data["choices"][0]["message"]
            content = message.get("content") or ""
            # Handle thinking / reasoning models where content might be empty or wrapped
            if not content.strip() and "reasoning_content" in message:
                content = message["reasoning_content"]
            return content.strip()

ai_provider = AIProviderService()

