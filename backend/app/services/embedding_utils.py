"""
Shared embedding utilities.

PURPOSE: Centralized embedding generation via Gemini Embedding API,
similarity comparison, and DynamoDB-compatible compression/decompression.

DEPENDS ON: config (GEMINI_API_KEY), http_client (connection pooling)
USED BY: execution_deduplication, atomic_unit_service, feed_search_service, news_utils, social_orchestrator
"""
import base64
import logging
import struct
from typing import List, Optional

import numpy as np

from app.config import settings
from app.services.http_client import get_http_client

logger = logging.getLogger(__name__)

GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta"
GEMINI_MODEL = "gemini-embedding-2-preview"
EMBEDDING_DIMENSIONS = 1536


def normalize_embedding(values: list[float]) -> list[float]:
    """Normalize embedding to unit length. Required for MRL truncation at < 3072 dims."""
    arr = np.array(values, dtype=np.float32)
    norm = np.linalg.norm(arr)
    if norm == 0:
        return values
    return (arr / norm).tolist()


async def generate_embedding(text: str, task_type: str = "SEMANTIC_SIMILARITY") -> List[float]:
    """Generate embedding for a single text via Gemini Embedding API."""
    client = await get_http_client()
    response = await client.post(
        f"{GEMINI_BASE_URL}/models/{GEMINI_MODEL}:embedContent?key={settings.gemini_api_key}",
        json={
            "model": f"models/{GEMINI_MODEL}",
            "content": {"parts": [{"text": text}]},
            "taskType": task_type,
            "outputDimensionality": EMBEDDING_DIMENSIONS,
        },
    )
    if response.status_code == 200:
        values = response.json()["embedding"]["values"]
        return normalize_embedding(values)
    logger.error(f"Gemini embedding failed: {response.text}")
    raise Exception(f"Embedding failed: {response.text}")


async def generate_embedding_multimodal(
    text: Optional[str] = None,
    image_bytes: Optional[bytes] = None,
    mime_type: str = "image/jpeg",
    task_type: str = "SEMANTIC_SIMILARITY",
) -> List[float]:
    """Generate embedding for mixed text + image content via Gemini."""
    parts = []
    if text:
        parts.append({"text": text})
    if image_bytes:
        b64 = base64.standard_b64encode(image_bytes).decode("utf-8")
        parts.append({"inline_data": {"mime_type": mime_type, "data": b64}})
    if not parts:
        raise ValueError("At least one of text or image_bytes must be provided")

    client = await get_http_client()
    response = await client.post(
        f"{GEMINI_BASE_URL}/models/{GEMINI_MODEL}:embedContent?key={settings.gemini_api_key}",
        json={
            "model": f"models/{GEMINI_MODEL}",
            "content": {"parts": parts},
            "taskType": task_type,
            "outputDimensionality": EMBEDDING_DIMENSIONS,
        },
    )
    if response.status_code == 200:
        values = response.json()["embedding"]["values"]
        return normalize_embedding(values)
    logger.error(f"Gemini multimodal embedding failed: {response.text}")
    raise Exception(f"Multimodal embedding failed: {response.text}")


async def generate_embeddings_batch(
    texts: List[str], task_type: str = "SEMANTIC_SIMILARITY"
) -> List[List[float]]:
    """Generate embeddings for multiple texts in a single Gemini batch call."""
    if not texts:
        return []

    embed_requests = [
        {
            "model": f"models/{GEMINI_MODEL}",
            "content": {"parts": [{"text": t}]},
            "taskType": task_type,
            "outputDimensionality": EMBEDDING_DIMENSIONS,
        }
        for t in texts
    ]

    client = await get_http_client()
    response = await client.post(
        f"{GEMINI_BASE_URL}/models/{GEMINI_MODEL}:batchEmbedContents?key={settings.gemini_api_key}",
        json={"requests": embed_requests},
    )
    if response.status_code == 200:
        data = response.json()
        return [normalize_embedding(e["values"]) for e in data["embeddings"]]
    else:
        logger.error(f"Gemini batch embeddings error: {response.status_code} - {response.text}")
        return []


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """Calculate cosine similarity between two vectors with zero-norm protection."""
    a_arr, b_arr = np.array(a), np.array(b)
    norm_a, norm_b = np.linalg.norm(a_arr), np.linalg.norm(b_arr)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return float(np.dot(a_arr, b_arr) / (norm_a * norm_b))


def compress_embedding(embedding: list[float]) -> str:
    """Compress embedding float array to base64 string (4x storage reduction).

    Format: struct-packed 32-bit floats, base64-encoded. Stored in DynamoDB
    as 'summary_embedding_compressed'. Changing this format breaks all
    existing stored embeddings.
    """
    packed = struct.pack(f"{len(embedding)}f", *embedding)
    return base64.b64encode(packed).decode()


def decompress_embedding(compressed: str) -> list[float]:
    """Decompress base64 string back to embedding float array.

    Inverse of compress_embedding(). The float count is inferred from
    byte length (each float = 4 bytes).
    """
    packed = base64.b64decode(compressed)
    return list(struct.unpack(f"{len(packed) // 4}f", packed))
