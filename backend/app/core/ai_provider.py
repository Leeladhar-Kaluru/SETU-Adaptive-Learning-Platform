import json
import re
import asyncio
import httpx
from typing import List, Dict, Any, Optional
from app.core.config import settings
from app.services.text_sanitize import sanitize_prose


class EmbeddingUnavailableError(RuntimeError):
    """The configured embedding provider could not produce valid vectors."""


class IncompleteGenerationError(RuntimeError):
    """The provider stopped before finishing a complete answer."""


_TRANSIENT_PROVIDER_MARKERS = (
    "model is unloaded",
    "unloaded",
    "has not started loading",
    "failed to load model",
    "engine protocol startup was aborted",
    "terminated",
    "loading",
)


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
        response = None
        delays = [1.0, 3.0, 6.0, 10.0]
        for attempt in range(len(delays) + 1):
            try:
                async with httpx.AsyncClient(timeout=60.0) as client:
                    response = await client.post(url, json=payload)
            except Exception as exc:
                if attempt >= len(delays):
                    raise EmbeddingUnavailableError("Embedding provider is unreachable.") from exc
                await asyncio.sleep(delays[attempt])
                continue

            if response.status_code == 200:
                break
            if attempt < len(delays) and _is_transient_response(response):
                # Local providers unload models under memory pressure; a
                # bounded retry lets them reload before the caller gives up.
                await asyncio.sleep(delays[attempt])
                continue
            raise EmbeddingUnavailableError(
                f"Embedding provider returned status {response.status_code}."
            )

        if response is None or response.status_code != 200:
            raise EmbeddingUnavailableError("Embedding provider did not return a response.")

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
        response_format: Optional[Dict[str, Any]] = None,
        require_complete: bool = False,
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
            resp = None
            delays = [2.0, 6.0, 12.0]
            for attempt in range(len(delays) + 1):
                try:
                    resp = await client.post(url, json=payload)
                except httpx.HTTPError:
                    # Local providers (LM Studio) abort in-flight requests when a
                    # model reloads or the server hiccups; retry like a 5xx.
                    resp = None
                if resp is not None and resp.status_code == 200:
                    break
                if attempt < len(delays):
                    await asyncio.sleep(delays[attempt])
                    continue
                break

            if resp is None or resp.status_code != 200:
                status_code = resp.status_code if resp is not None else "unreachable"
                body = resp.text if resp is not None else ""
                raise RuntimeError(
                    f"LLM chat completion failed with status {status_code}: {body}"
                )

            data = resp.json()
            choice = (data.get("choices") or [{}])[0]
            message = choice.get("message") or {}
            content = message.get("content") or ""
            if not content.strip() and "reasoning_content" in message:
                content = message["reasoning_content"]
            if response_format:
                # When caller requested JSON, preserve the raw JSON syntax untouched
                # so prose sanitization does not mangle JSON braces, keys, or types.
                # Caller will parse JSON and sanitize prose fields with sanitize_tree().
                return content.strip()
            cleaned = _clean_generated_text(content)
            # Local reasoning models can spend the token budget on hidden
            # reasoning and return a half-written sentence, sometimes with a
            # normal finish reason. If trailing text was cut off, recover the
            # last fully completed sentence before checking completeness.
            if not _is_complete_prose(cleaned):
                last_punct = max(cleaned.rfind("."), cleaned.rfind("!"), cleaned.rfind("?"))
                if last_punct > 40:
                    cleaned = cleaned[: last_punct + 1].strip()

            if require_complete and not _is_complete_prose(cleaned):
                raise IncompleteGenerationError(
                    "The model stopped before finishing its answer."
                )
            if not cleaned:
                raise IncompleteGenerationError("The model returned an empty answer.")
            return cleaned


_GENERATED_CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")


def _is_transient_response(response: httpx.Response) -> bool:
    if response.status_code >= 500:
        return True
    if response.status_code != 400:
        return False
    body = (response.text or "").lower()
    return any(marker in body for marker in _TRANSIENT_PROVIDER_MARKERS)


def _clean_generated_text(text: str) -> str:
    """Removes corrupt bytes, control characters and LaTeX/markdown artifacts."""
    cleaned = str(text).replace("\r\n", "\n").replace("\r", "\n")
    # A replacement character means the provider emitted an invalid byte.
    cleaned = re.sub(r"\ufffd\?*", " ", cleaned)
    cleaned = _GENERATED_CONTROL_CHARS.sub("", cleaned)
    cleaned = re.sub(r"[ \t]+\n", "\n", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    cleaned = re.sub(r"[ \t]{2,}", " ", cleaned)
    # Convert raw LaTeX ($82^{\circ}30' E$) and markdown emphasis into plain
    # unicode prose so students never see dollar signs or asterisks.
    return sanitize_prose(cleaned)


def _is_complete_prose(text: str) -> bool:
    """True when prose ends like a finished answer, not a cut-off sentence.

    A page reference or numeric answer may legitimately end in a digit. Closing
    quotes and brackets are ignored. Everything else must end in terminal
    punctuation; otherwise the caller should retry instead of storing it.
    """
    stripped = (text or "").rstrip()
    while stripped and stripped[-1] in "\"')]}’”":
        stripped = stripped[:-1].rstrip()
    if not stripped:
        return False
    return stripped[-1] in ".!?" or stripped[-1].isdigit()


ai_provider = AIProviderService()

