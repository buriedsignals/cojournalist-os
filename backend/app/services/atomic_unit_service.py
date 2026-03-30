"""
Atomic Unit Service

PURPOSE: Extract atomic information units from search-based scout results.
Each article yields 1-3 atomic units (facts, events, entity updates) that
power the Feed panel and notification decisions.

DEPENDS ON: config (AWS region), openrouter (LLM extraction), embedding_utils
    (batch embeddings, compress/decompress, cosine_similarity),
    locale_data (language names), schemas/scouts (GeocodedLocation)
USED BY: services/execute_pipeline.py, services/scout_service.py

DEDUPLICATION:
- Within-run dedup: removes near-duplicate units from same execution (0.75 threshold)
- Cross-run dedup: compares against recent facts from same scout (0.85 threshold)
  - URL-based: skips units from already-processed URLs (normalized for variations)
  - Embedding-based: catches semantic duplicates even from new URLs
  Controls notification decisions - only new facts trigger notifications.

CRITICAL: The process_results() method is the gatekeeper for all notifications.
Its return value (new_facts vs all_duplicates) determines whether the pipeline
sends an email. Removing or short-circuiting the dedup logic will cause
duplicate notifications on every scheduled run.

TABLE: information-units
KEY: USER#{user_id}#LOC#{country}#{state}#{city} (or USER#{user_id}#TOPIC#{topic} or USER#{user_id}#DATA#{dataset_id})
SK: UNIT#{timestamp_ms}#{unit_id}
GSI: scout-units-index (GSI2PK: USER#{user_id}#SCOUT#{scout_id}, GSI2SK: UNIT#{timestamp_ms})
"""
import asyncio
import json
import logging
import re
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional
from urllib.parse import urlparse, urlunparse, parse_qs, urlencode

from app.services.openrouter import openrouter_chat
from app.services.embedding_utils import (
    compress_embedding,
    decompress_embedding,
    cosine_similarity,
    generate_embeddings_batch,
)
from app.services.locale_data import LANGUAGE_NAMES
from app.schemas.scouts import GeocodedLocation

logger = logging.getLogger(__name__)


# =============================================================================
# URL Normalization (for deduplication)
# =============================================================================

# Tracking/campaign parameters to strip from URLs
TRACKING_PARAMS = {
    "utm_source", "utm_medium", "utm_campaign", "utm_content", "utm_term",
    "ref", "source", "fbclid", "gclid", "dclid", "msclkid",
    "mc_cid", "mc_eid", "oly_enc_id", "vero_id", "s_kwcid",
}


_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def normalize_url(url: str) -> str:
    """
    Normalize URL for deduplication comparison.

    Handles common URL variations:
    - Strips trailing slashes from path
    - Removes tracking/campaign query parameters
    - Removes fragment identifiers
    - Lowercases domain (preserves path case for case-sensitive servers)
    - Normalizes to https

    Args:
        url: The URL to normalize

    Returns:
        Normalized URL string for comparison
    """
    if not url:
        return ""

    try:
        parsed = urlparse(url.strip())

        # Lowercase the domain only (path may be case-sensitive)
        netloc = parsed.netloc.lower()

        # Remove trailing slash from path (but keep root "/" as is)
        path = parsed.path.rstrip("/") if parsed.path != "/" else "/"

        # Filter out tracking parameters
        if parsed.query:
            query_params = parse_qs(parsed.query, keep_blank_values=False)
            filtered_params = {
                k: v for k, v in query_params.items()
                if k.lower() not in TRACKING_PARAMS
            }
            # Sort params for consistent ordering
            query = urlencode(sorted(filtered_params.items()), doseq=True) if filtered_params else ""
        else:
            query = ""

        # Reconstruct without fragment, normalize to https
        return urlunparse(("https", netloc, path, "", query, ""))

    except Exception as e:
        logger.warning(f"Failed to normalize URL '{url}': {e}")
        return url.strip().lower()


# =============================================================================
# Processing Result
# =============================================================================

@dataclass
class ProcessingResult:
    """Result of processing articles into atomic units with dedup info."""
    new_facts: list[dict]
    duplicate_facts: list[dict]
    all_duplicates: bool


# =============================================================================
# LLM Extraction Prompt
# =============================================================================

EXTRACTION_SYSTEM_PROMPT_TEMPLATE = """You are a journalist's research assistant. Extract atomic information units from news articles.

CRITICAL RULE - 5W1H COMPLETENESS:
Every statement MUST be understandable without reading the original article.
Include the essential 5W1H elements when available:
- WHO: Name specific people/organizations (not "officials" or "the company")
- WHAT: The specific action, decision, or fact
- WHEN: Date, time, or time reference
- WHERE: Location (city, region, country) if relevant

RULES:
1. Extract 1-3 DISTINCT factual units from the article
2. Each unit must be a SINGLE, verifiable statement
3. Prioritize: facts with numbers/dates > events > entity updates
4. Each unit must be SELF-CONTAINED (understandable without context)
5. Include ALL relevant entities (people, organizations, places)
6. Preserve source attribution in the statement itself
7. Write ALL statements in {language}

DATE EXTRACTION:
- Extract the most relevant date from the fact as "date" in YYYY-MM-DD format
- Use the event/decision date, not the publication date
- If no specific date is mentioned or inferrable, use null
- For future events ("next Monday", "March 2025"), resolve to an actual date using the current date as reference

UNIT TYPES:
- "fact": Verifiable statement with specific data (numbers, dates, decisions)
- "event": Something that happened or will happen (with time context)
- "entity_update": Change in status of a person, organization, or place

GOOD vs BAD EXAMPLES:
❌ BAD: "The council approved the budget."
   (Missing: WHO specifically? WHAT budget? WHEN? WHERE?)
✅ GOOD: "The Zurich city council approved a CHF 50M budget for public transit expansion on January 10, 2025."
   (Has: WHO=Zurich city council, WHAT=CHF 50M transit budget, WHEN=Jan 10 2025, WHERE=Zurich)

❌ BAD: "He announced new policies for the region."
   (Missing: WHO is 'he'? WHAT policies? WHICH region?)
✅ GOOD: "Mayor Hans Müller announced a 20% rent cap policy for Zurich's northern districts on Monday."
   (Has: WHO=Mayor Hans Müller, WHAT=20% rent cap, WHEN=Monday, WHERE=Zurich's northern districts)

❌ BAD: "Construction will begin soon."
   (Missing: WHAT construction? WHEN specifically? WHERE?)
✅ GOOD: "Construction of the new Limmattalbahn tram line begins in March 2025, connecting Zurich to Killwangen."
   (Has: WHAT=Limmattalbahn tram, WHEN=March 2025, WHERE=Zurich to Killwangen)

OUTPUT FORMAT (JSON):
{{
  "units": [
    {{
      "statement": "The Zurich city council approved a CHF 50M budget for public transit expansion on January 10, 2025.",
      "type": "fact",
      "entities": ["Zurich city council", "public transit"],
      "date": "2025-01-10"
    }},
    {{
      "statement": "Zurich's population has grown by 12% over the past decade, according to the Federal Statistical Office.",
      "type": "fact",
      "entities": ["Zurich", "Federal Statistical Office"],
      "date": null
    }}
  ]
}}

QUALITY GUIDELINES:
- NO opinions or subjective assessments
- NO speculation or predictions without source backing
- If article lacks concrete facts, extract fewer units (even 0)
- Prefer specific over vague ("$50M" not "large amount")
- Each statement should be 1-2 sentences maximum
- ALWAYS include enough context for the statement to stand alone"""


class AtomicUnitService:
    """Extract and store atomic information units from scout executions."""

    TABLE_NAME = "information-units"
    TTL_DAYS = 90
    MAX_UNITS_PER_ARTICLE = 3  # Default for search-based scouts
    MAX_UNITS_WEB_SCOUT = 8    # Higher limit for web scouts (homepage monitoring)

    # Within-run dedup: units from same execution
    # Lowered from 0.85 to 0.75 to catch paraphrased facts with similar meaning
    WITHIN_RUN_SIMILARITY_THRESHOLD = 0.75

    # Cross-run dedup: units from previous scout runs
    # Lowered from 0.90 to 0.85 to catch semantic duplicates with slight wording variations
    CROSS_RUN_SIMILARITY_THRESHOLD = 0.85
    MAX_RECENT_FACTS = 50

    def __init__(self, unit_storage=None):
        if unit_storage is None:
            from app.dependencies.providers import get_unit_storage
            unit_storage = get_unit_storage()
        self.unit_storage = unit_storage

    # =========================================================================
    # Recent Facts Retrieval (for cross-run dedup + prompt injection)
    # =========================================================================

    async def get_recent_facts(
        self,
        user_id: str,
        scout_id: str,
        limit: int = 50,
    ) -> list[dict]:
        """
        Get recent facts for this scout (for prompt injection and dedup).

        Uses the scout-units-index GSI to efficiently query facts by scout.

        Returns:
            List of dicts with statement, embedding, source_url
        """
        try:
            records = await self.unit_storage.get_units_by_scout(user_id, scout_id, limit=limit)
            facts = []
            for item in records:
                embedding = None
                if item.get("embedding_compressed"):
                    try:
                        embedding = decompress_embedding(item["embedding_compressed"])
                    except Exception as e:
                        logger.warning(f"Failed to decompress embedding: {e}")
                facts.append({
                    "statement": item.get("statement", ""),
                    "embedding": embedding,
                    "source_url": item.get("source_url", ""),
                })
            logger.info(f"Retrieved {len(facts)} recent facts for scout {scout_id}")
            return facts
        except Exception as e:
            logger.error(f"Failed to get recent facts: {e}")
            return []

    # =========================================================================
    # Key Building
    # =========================================================================

    def _build_pk(self, user_id: str, location: Optional[GeocodedLocation] = None, topic: Optional[str] = None) -> str:
        if location:
            state = location.state or "_"
            city = location.city or "_"
            return f"USER#{user_id}#LOC#{location.country}#{state}#{city}"
        elif topic:
            return f"USER#{user_id}#TOPIC#{topic}"
        else:
            raise ValueError("Either location or topic must be provided")

    def _build_sk(self, timestamp_ms: int, unit_id: str) -> str:
        return f"UNIT#{timestamp_ms}#{unit_id}"

    # =========================================================================
    # LLM Extraction
    # =========================================================================

    async def _extract_atomic_units(
        self,
        title: str,
        content: str,
        source_url: str,
        language_name: str = "English",
        scout_type: str = "pulse",
        published_date: Optional[str] = None,
    ) -> list[dict]:
        """Use LLM to extract atomic units from article.

        Web scouts get higher limits (8 units, 6000 chars) since they monitor
        full pages that may contain multiple stories.
        """
        source_domain = urlparse(source_url).netloc

        # Web scouts get higher content limit (full page monitoring)
        content_limit = 6000 if scout_type == "web" else 3000
        max_units = self.MAX_UNITS_WEB_SCOUT if scout_type == "web" else self.MAX_UNITS_PER_ARTICLE

        system_prompt = EXTRACTION_SYSTEM_PROMPT_TEMPLATE.format(language=language_name)

        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        user_prompt = f"""Extract atomic information units from this article.

CURRENT DATE: {today}
ARTICLE PUBLISHED: {published_date or "unknown"}
ARTICLE TITLE: {title}
SOURCE: {source_domain}
CONTENT:
{content[:content_limit]}

Extract 1-{max_units} atomic units. If the article lacks concrete facts, return fewer units."""

        try:
            response = await openrouter_chat(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                max_tokens=800 if scout_type == "web" else 500,  # More tokens for more units
                temperature=0.1,
                response_format={"type": "json_object"}
            )

            result = json.loads(response["content"])
            units = result.get("units", [])

            valid_units = []
            for unit in units[:max_units]:
                if (
                    isinstance(unit, dict) and
                    unit.get("statement") and
                    unit.get("type") in ("fact", "event", "entity_update")
                ):
                    raw_date = unit.get("date")
                    valid_units.append({
                        "statement": unit["statement"][:500],
                        "type": unit["type"],
                        "entities": unit.get("entities", [])[:10],
                        "date": raw_date if raw_date and _DATE_RE.match(raw_date) else None,
                    })

            logger.info(f"Extracted {len(valid_units)} units from: {title[:50]}")
            return valid_units

        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse extraction response: {e}")
            return []
        except Exception as e:
            logger.error(f"LLM extraction failed: {e}")
            return []

    # =========================================================================
    # Item Building (separated from storage for batch writes)
    # =========================================================================

    def _build_unit_item(
        self,
        article_id: str,
        statement: str,
        unit_type: str,
        entities: list[str],
        source_url: str,
        source_domain: str,
        source_title: str,
        embedding: Optional[list[float]],
        scout_id: str,
        scout_type: str,
        user_id: str,
        location: Optional[GeocodedLocation] = None,
        topic: Optional[str] = None,
        date: Optional[str] = None,
    ) -> tuple[dict, dict]:
        """Build a DynamoDB item and a return dict for a single atomic unit.

        Separates item construction from storage so process_results() can
        batch-write all items in a single DynamoDB batch_writer call.

        Returns:
            (dynamo_item, return_dict) tuple
        """
        timestamp_ms = int(time.time() * 1000)
        unit_id = str(uuid.uuid4())
        pk = self._build_pk(user_id, location=location, topic=topic)
        sk = self._build_sk(timestamp_ms, unit_id)

        coordinates = None
        if location and getattr(location, 'coordinates', None):
            coordinates = {
                "lat": Decimal(str(location.coordinates.lat)),
                "lon": Decimal(str(location.coordinates.lon)),
            }

        item = {
            "PK": pk,
            "SK": sk,
            "unit_id": unit_id,
            "article_id": article_id,
            "user_id": user_id,
            "scout_id": scout_id,
            "scout_type": scout_type,
            "statement": statement,
            "unit_type": unit_type,
            "entities": entities,
            "source_url": source_url,
            "source_domain": source_domain,
            "source_title": source_title,
            "created_at": datetime.utcnow().isoformat() + "Z",
            "used_in_article": False,
            "ttl": int(time.time()) + (self.TTL_DAYS * 24 * 60 * 60),
            "GSI1PK": f"ARTICLE#{article_id}",
            "GSI1SK": f"UNIT#{unit_id}",
            # GSI for per-scout queries (cross-run dedup)
            "GSI2PK": f"USER#{user_id}#SCOUT#{scout_id}",
            "GSI2SK": f"UNIT#{timestamp_ms}",
        }

        if location:
            item["location"] = {
                "displayName": location.displayName,
                "city": location.city,
                "state": location.state,
                "country": location.country,
                "coordinates": coordinates,
            }

        if topic:
            item["topic"] = topic

        if date:
            item["date"] = date

        if embedding:
            item["embedding_compressed"] = compress_embedding(embedding)

        return_dict = {
            "unit_id": unit_id,
            "article_id": article_id,
            "pk": pk,
            "sk": sk,
            "statement": statement,
            "unit_type": unit_type,
            "entities": entities,
            "source_url": source_url,
            "source_domain": source_domain,
            "source_title": source_title,
            "scout_type": scout_type,
            "scout_id": scout_id,
            "created_at": item["created_at"],
            "used_in_article": False,
            "date": date,
        }

        return item, return_dict

    # =========================================================================
    # Public API
    # =========================================================================

    async def process_results(
        self,
        results: list[dict],
        scout_id: str,
        scout_type: str,
        user_id: str,
        location: Optional[GeocodedLocation] = None,
        topic: Optional[str] = None,
        language: str = "English",
        recent_facts: Optional[list[dict]] = None,
    ) -> ProcessingResult:
        """
        Process scout results into atomic information units with cross-run dedup.

        1. Extract 1-3 atomic units per article using LLM (IN PARALLEL)
        2. Within-run dedup: remove near-duplicates from this execution
        3. Cross-run dedup: compare against recent facts from previous runs
        4. Store only NEW facts (duplicates are discarded entirely)

        Args:
            recent_facts: List of recent facts from get_recent_facts() for cross-run dedup.
                         Each dict should have 'statement', 'embedding', 'source_url'.

        Returns:
            ProcessingResult with new_facts, duplicate_facts, and all_duplicates flag
        """
        valid_articles = [
            r for r in results
            if r.get("title") and r.get("url")
        ]

        if not valid_articles:
            logger.info("No valid articles to process")
            return ProcessingResult(new_facts=[], duplicate_facts=[], all_duplicates=True)

        # Deduplicate articles by normalized URL before extraction
        # This prevents extracting units from the same article multiple times
        seen_urls = set()
        unique_articles = []
        for article in valid_articles:
            normalized = normalize_url(article.get("url", ""))
            if normalized and normalized not in seen_urls:
                seen_urls.add(normalized)
                unique_articles.append(article)

        if len(unique_articles) < len(valid_articles):
            logger.info(f"Deduplicated {len(valid_articles)} articles to {len(unique_articles)} unique URLs")

        valid_articles = unique_articles

        # Extract units from all articles IN PARALLEL
        extraction_tasks = [
            self._extract_atomic_units(
                title=r.get("title", ""),
                content=r.get("content", r.get("summary", "")),
                source_url=r.get("url", ""),
                language_name=language,
                scout_type=scout_type,
                published_date=r.get("date"),
            )
            for r in valid_articles
        ]

        logger.info(f"Extracting units from {len(extraction_tasks)} articles in parallel")
        all_extracted = await asyncio.gather(*extraction_tasks, return_exceptions=True)

        # Collect all units with metadata for batch embedding
        all_units_meta = []  # (article_index, unit_data)
        for i, extracted in enumerate(all_extracted):
            if isinstance(extracted, Exception):
                logger.warning(f"Extraction failed for article {i}: {extracted}")
                continue
            if not extracted:
                continue
            for unit_data in extracted:
                all_units_meta.append((i, unit_data))

        if not all_units_meta:
            logger.info("No units extracted from articles")
            return ProcessingResult(new_facts=[], duplicate_facts=[], all_duplicates=True)

        # Batch generate embeddings for all statements at once
        all_statements = [u[1]["statement"] for u in all_units_meta]
        embeddings_list = []
        if all_statements:
            try:
                embeddings_list = await generate_embeddings_batch(
                    all_statements, "FACT_VERIFICATION"
                )
            except Exception as e:
                logger.error(f"Batch embedding generation failed: {e}")

        # Within-run dedup: remove near-duplicate units using cosine similarity
        if embeddings_list and len(embeddings_list) == len(all_units_meta):
            keep = [True] * len(all_units_meta)
            for i in range(len(all_units_meta)):
                if not keep[i]:
                    continue
                for j in range(i + 1, len(all_units_meta)):
                    if not keep[j]:
                        continue
                    sim = cosine_similarity(embeddings_list[i], embeddings_list[j])
                    # Log close comparisons to help tune threshold
                    if sim >= 0.70:
                        logger.debug(
                            f"[Within-run dedup] Similarity {sim:.3f} between:\n"
                            f"  A: {all_units_meta[i][1]['statement'][:80]}\n"
                            f"  B: {all_units_meta[j][1]['statement'][:80]}"
                        )
                    if sim >= self.WITHIN_RUN_SIMILARITY_THRESHOLD:
                        # Keep the longer/more detailed statement
                        if len(all_units_meta[i][1]["statement"]) >= len(all_units_meta[j][1]["statement"]):
                            keep[j] = False
                        else:
                            keep[i] = False
                            break  # i is removed, no need to compare further

            dedup_count = keep.count(False)
            if dedup_count > 0:
                logger.info(f"Within-run dedup removed {dedup_count} near-duplicate units")
                all_units_meta = [u for u, k in zip(all_units_meta, keep) if k]
                embeddings_list = [e for e, k in zip(embeddings_list, keep) if k]

        # Cross-run dedup: compare against recent facts from previous scout runs
        # This controls notification decisions - only new facts trigger notifications
        cross_run_duplicates = []

        # URL-based deduplication: skip units from already-processed URLs
        # This prevents re-extracting facts from the same article across runs
        # URLs are normalized to handle variations (trailing slashes, tracking params, etc.)
        if recent_facts and all_units_meta:
            recent_urls = {
                normalize_url(f.get("source_url", ""))
                for f in recent_facts
                if f.get("source_url")
            }
            if recent_urls:
                keep = [True] * len(all_units_meta)
                for i in range(len(all_units_meta)):
                    article_i = all_units_meta[i][0]
                    source_url = valid_articles[article_i].get("url", "")
                    normalized_url = normalize_url(source_url)
                    if normalized_url and normalized_url in recent_urls:
                        keep[i] = False
                        cross_run_duplicates.append({
                            "statement": all_units_meta[i][1]["statement"],
                            "source_url": source_url,
                            "reason": "url_already_processed",
                        })

                url_dedup_count = keep.count(False)
                if url_dedup_count > 0:
                    logger.info(f"URL-based dedup removed {url_dedup_count} units from already-processed articles")
                    all_units_meta = [u for u, k in zip(all_units_meta, keep) if k]
                    embeddings_list = [e for e, k in zip(embeddings_list, keep) if k]

        # Embedding-based cross-run dedup for units from new URLs
        if recent_facts and embeddings_list and len(embeddings_list) == len(all_units_meta):
            # Get embeddings from recent facts that have them
            recent_embeddings = [
                (f["embedding"], f["statement"])
                for f in recent_facts
                if f.get("embedding")
            ]

            if recent_embeddings:
                keep = [True] * len(all_units_meta)
                for i in range(len(all_units_meta)):
                    if not keep[i]:
                        continue
                    new_embedding = embeddings_list[i]
                    statement = all_units_meta[i][1]["statement"]

                    for recent_emb, recent_stmt in recent_embeddings:
                        sim = cosine_similarity(new_embedding, recent_emb)
                        if sim >= self.CROSS_RUN_SIMILARITY_THRESHOLD:
                            keep[i] = False
                            cross_run_duplicates.append({
                                "statement": statement,
                                "similar_to": recent_stmt[:100],
                                "similarity": sim,
                            })
                            break  # Found duplicate, no need to check more

                cross_run_count = keep.count(False)
                if cross_run_count > 0:
                    logger.info(f"Cross-run dedup removed {cross_run_count} duplicate units")
                    # Filter out cross-run duplicates
                    all_units_meta = [u for u, k in zip(all_units_meta, keep) if k]
                    embeddings_list = [e for e, k in zip(embeddings_list, keep) if k]

        # Check if all facts were duplicates
        if not all_units_meta:
            logger.info("All extracted facts were duplicates - nothing new to store")
            return ProcessingResult(
                new_facts=[],
                duplicate_facts=cross_run_duplicates,
                all_duplicates=True,
            )

        # Build all DynamoDB items and return dicts first, then batch-write
        all_new_units = []
        dynamo_items = []
        article_ids = {}  # article_index -> uuid

        for idx, (article_i, unit_data) in enumerate(all_units_meta):
            article = valid_articles[article_i]
            if article_i not in article_ids:
                article_ids[article_i] = str(uuid.uuid4())
            article_id = article_ids[article_i]

            title = article.get("title", "")
            source_url = article.get("url", "")
            source_domain = urlparse(source_url).netloc

            statement = unit_data["statement"]
            unit_type = unit_data["type"]
            entities = unit_data.get("entities", [])

            embedding = embeddings_list[idx] if idx < len(embeddings_list) else None

            dynamo_item, return_dict = self._build_unit_item(
                article_id=article_id,
                statement=statement,
                unit_type=unit_type,
                entities=entities,
                source_url=source_url,
                source_domain=source_domain,
                source_title=title,
                embedding=embedding,
                scout_id=scout_id,
                scout_type=scout_type,
                user_id=user_id,
                location=location,
                topic=topic,
                date=unit_data.get("date"),
            )

            dynamo_items.append(dynamo_item)
            all_new_units.append(return_dict)

        # Store units via adapter (adapter handles batch writing and key construction)
        try:
            await self.unit_storage.store_units(user_id, scout_id, all_new_units)
            logger.info(f"Stored {len(all_new_units)} units via adapter")
        except Exception as e:
            logger.error(f"Failed to store units: {e}")

        logger.info(
            f"Processed {len(valid_articles)} articles: "
            f"{len(all_new_units)} new facts stored, "
            f"{len(cross_run_duplicates)} cross-run duplicates discarded"
        )

        return ProcessingResult(
            new_facts=all_new_units,
            duplicate_facts=cross_run_duplicates,
            all_duplicates=False,
        )

    async def _store_unit(
        self,
        article_id: str,
        statement: str,
        unit_type: str,
        entities: list[str],
        source_url: str,
        source_domain: str,
        source_title: str,
        embedding: Optional[list[float]],
        scout_id: str,
        scout_type: str,
        user_id: str,
        location: Optional[GeocodedLocation] = None,
        topic: Optional[str] = None,
        date: Optional[str] = None,
    ) -> dict:
        """Store a single atomic information unit in DynamoDB.

        NOTE: This method is kept for backward compatibility. The main
        process_results() path now uses _build_unit_item() + batch_writer
        for better performance. This method is only used by external callers.
        """
        dynamo_item, return_dict = self._build_unit_item(
            article_id=article_id,
            statement=statement,
            unit_type=unit_type,
            entities=entities,
            source_url=source_url,
            source_domain=source_domain,
            source_title=source_title,
            embedding=embedding,
            scout_id=scout_id,
            scout_type=scout_type,
            user_id=user_id,
            location=location,
            topic=topic,
            date=date,
        )

        await self.unit_storage.store_units(user_id, scout_id, [return_dict])

        return return_dict
