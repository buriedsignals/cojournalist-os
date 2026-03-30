"""
Execution Deduplication Service

Prevents duplicate notifications by comparing summary embeddings across
recent execution records. Delegates storage to ExecutionStoragePort adapter.

Business logic (embedding generation, cosine similarity, summary generation)
stays here. Only raw storage operations go through the adapter.
"""
import logging
from typing import Optional

from app.services.openrouter import openrouter_chat
from app.services.embedding_utils import (
    generate_embedding,
    cosine_similarity,
    decompress_embedding,
)

logger = logging.getLogger(__name__)

SUMMARY_SYSTEM_PROMPT = """Summarize the following scout execution results in exactly ONE sentence (max 150 characters).
Focus on the key finding or topic. Preserve the original language of the content.
Output ONLY the summary sentence, nothing else."""


class ExecutionDeduplicationService:
    """Execution-level deduplication using summary embeddings."""

    SIMILARITY_THRESHOLD = 0.85
    MAX_COMPARISONS = 20
    RECENT_FINDINGS_LIMIT = 5

    def __init__(self, execution_storage=None):
        if execution_storage is None:
            from app.dependencies.providers import get_execution_storage
            execution_storage = get_execution_storage()
        self.storage = execution_storage

    async def get_recent_findings(
        self,
        user_id: str,
        scout_name: str,
        limit: int = 5,
    ) -> list[dict]:
        """Get recent non-duplicate execution summaries for prompt injection."""
        try:
            records = await self.storage.get_recent_executions(user_id, scout_name, limit=limit)
            findings = []
            for item in records:
                if item.get("is_duplicate"):
                    continue
                summary = item.get("summary_text", "")
                if summary:
                    findings.append({
                        "summary_text": summary,
                        "completed_at": item.get("completed_at", ""),
                    })
            return findings
        except Exception as e:
            logger.error(f"Failed to get recent findings: {e}")
            return []

    async def get_latest_content_hash(
        self,
        user_id: str,
        scout_name: str,
    ) -> Optional[str]:
        """Get the most recent content_hash for plain scrape change detection."""
        try:
            return await self.storage.get_latest_content_hash(user_id, scout_name)
        except Exception as e:
            logger.error(f"Failed to get latest content hash: {e}")
            return None

    async def check_duplicate(
        self,
        user_id: str,
        scout_name: str,
        summary_text: str,
    ) -> tuple[bool, float, Optional[list[float]]]:
        """Check if this execution's summary is a duplicate of recent ones.

        Business logic: generates embedding, fetches recent records from adapter,
        decompresses stored embeddings, computes cosine similarity.

        Returns (is_duplicate, highest_similarity, embedding).
        """
        if not summary_text:
            return False, 0.0, None

        try:
            new_embedding = await generate_embedding(summary_text, "SEMANTIC_SIMILARITY")

            records = await self.storage.get_recent_embeddings(
                user_id, scout_name, limit=self.MAX_COMPARISONS
            )

            max_similarity = 0.0
            for item in records:
                compressed = item.get("summary_embedding_compressed")
                if not compressed:
                    continue
                stored_embedding = decompress_embedding(compressed)
                similarity = cosine_similarity(new_embedding, stored_embedding)
                max_similarity = max(max_similarity, similarity)
                if similarity >= self.SIMILARITY_THRESHOLD:
                    logger.info(
                        f"Execution duplicate detected for {scout_name}: "
                        f"sim={similarity:.3f}, summary='{summary_text[:50]}'"
                    )
                    return True, similarity, new_embedding

            return False, max_similarity, new_embedding

        except Exception as e:
            logger.error(f"Duplicate check failed: {e}")
            return False, 0.0, None

    async def store_execution(
        self,
        user_id: str,
        scout_name: str,
        scout_type: str,
        summary_text: str,
        is_duplicate: bool,
        started_at: str,
        embedding: Optional[list[float]] = None,
        content_hash: Optional[str] = None,
        provider: Optional[str] = None,
    ) -> dict:
        """Store an execution record via adapter."""
        try:
            result = await self.storage.store_execution(
                user_id=user_id,
                scout_name=scout_name,
                scout_type=scout_type,
                summary_text=summary_text,
                is_duplicate=is_duplicate,
                started_at=started_at,
                embedding=embedding,
                content_hash=content_hash,
                provider=provider,
            )
            logger.info(f"Stored execution record for {scout_name} (duplicate={is_duplicate})")
            return result or {}
        except Exception as e:
            logger.error(f"Failed to store execution record: {e}")
            return {}

    async def generate_summary_from_facts(self, new_facts: list[dict]) -> str:
        """Generate a 1-sentence summary from new facts (LLM — no storage)."""
        if not new_facts:
            return "No new findings"

        statements = [f.get("statement", "")[:200] for f in new_facts[:5] if f.get("statement")]
        if not statements:
            return "No new findings"

        content = "New findings:\n" + "\n".join(f"- {s}" for s in statements)

        try:
            response = await openrouter_chat(
                messages=[
                    {"role": "system", "content": SUMMARY_SYSTEM_PROMPT},
                    {"role": "user", "content": content[:2000]},
                ],
                max_tokens=100,
                temperature=0.0,
            )
            return response["content"].strip()[:150]
        except Exception as e:
            logger.error(f"Summary generation from facts failed: {e}")
            return statements[0][:150] if statements else "No new findings"
