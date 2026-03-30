"""
Export Generator Service

PURPOSE: Generate article drafts from selected atomic information units using
LLM. Groups units by type (facts, events, entity_updates) and optionally
re-fetches original source URLs via Firecrawl for richer context in prompts.

DEPENDS ON: http_client (connection pooling), config (API keys)
USED BY: routers/export.py

Uses low temperature (0.2) for factual, non-hallucinating output.
Source enrichment re-fetches via Firecrawl to inject full article content
into the AI prompt for better drafts.
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections import Counter
from urllib.parse import urlparse

from ..config import settings
from .http_client import get_http_client
from .locale_data import LANGUAGE_NAMES
from .url_validator import is_safe_external_url

logger = logging.getLogger(__name__)


class ExportGeneratorService:
    """Generate exports from atomic information units using OpenRouter."""

    MODEL = settings.llm_model
    TEMPERATURE = 0.2  # Low for factual, no hallucination
    MAX_TOKENS = 2500

    def __init__(self):
        self.api_key = settings.openrouter_api_key

    def _format_units_by_type(self, units: list[dict]) -> str:
        """Group and format units by type for the prompt."""
        facts = []
        events = []
        entity_updates = []

        for i, u in enumerate(units, 1):
            unit_type = u.get("unit_type", "fact")
            statement = u.get("statement", "")
            source_domain = u.get("source_domain", "unknown")

            # Include additional sources if present
            sources = [source_domain] if source_domain else []
            for additional in u.get("additional_sources", []):
                if additional.get("domain"):
                    sources.append(additional["domain"])
            sources_str = ", ".join(sources[:3]) if sources else "source"

            # Include entities if present for better context
            entities = u.get("entities", [])
            entities_str = f" [entities: {', '.join(entities[:5])}]" if entities else ""

            entry = f"[{i}] {statement} ({sources_str}){entities_str}"

            if unit_type == "fact":
                facts.append(entry)
            elif unit_type == "event":
                events.append(entry)
            elif unit_type == "entity_update":
                entity_updates.append(entry)
            else:
                facts.append(entry)  # Default to fact

        sections = []
        if facts:
            sections.append("FACTS:\n" + "\n".join(facts))
        if events:
            sections.append("EVENTS:\n" + "\n".join(events))
        if entity_updates:
            sections.append("ENTITY UPDATES:\n" + "\n".join(entity_updates))

        return "\n\n".join(sections)

    def _analyze_entities(self, units: list[dict]) -> list[str]:
        """
        Analyze entity frequency across all units.
        Returns top entities that appear in multiple units.
        """
        entity_counter = Counter()
        for u in units:
            entities = u.get("entities", [])
            for entity in entities:
                if entity:  # Skip empty strings
                    entity_counter[entity.strip()] += 1

        # Get entities that appear in 2+ units, sorted by frequency
        frequent_entities = [
            entity for entity, count in entity_counter.most_common(10)
            if count >= 2
        ]
        return frequent_entities

    def _get_topics(self, units: list[dict]) -> list[str]:
        """Extract unique topics from units."""
        topics = set()
        for u in units:
            topic = u.get("topic")
            if topic:
                topics.add(topic)
        return list(topics)[:5]  # Cap at 5 topics

    @staticmethod
    def _is_safe_source_url(url: str) -> bool:
        """Validate source URL for safe fetching (SSRF protection)."""
        return is_safe_external_url(url)

    async def _fetch_source_content(self, urls: list[str], timeout_per_source: float = 5.0) -> dict[str, str]:
        """
        Fetch content from source URLs for enrichment.
        Uses Firecrawl scrape endpoint with short timeout.

        Args:
            urls: List of URLs to fetch
            timeout_per_source: Timeout per source in seconds

        Returns:
            Dict mapping URL -> content (markdown)
        """
        if not urls:
            return {}

        firecrawl_key = settings.firecrawl_api_key
        if not firecrawl_key:
            logger.warning("[ExportGenerator] No Firecrawl API key, skipping source enrichment")
            return {}

        async def fetch_single(url: str) -> tuple[str, str]:
            """Fetch a single URL, returning (url, content) or (url, '') on failure."""
            try:
                client = await get_http_client()
                response = await asyncio.wait_for(
                    client.post(
                        "https://api.firecrawl.dev/v2/scrape",
                        headers={
                            "Authorization": f"Bearer {firecrawl_key}",
                            "Content-Type": "application/json"
                        },
                        json={
                            "url": url,
                            "formats": ["markdown"],
                            "maxAge": 86400000  # 24 hour cache
                        }
                    ),
                    timeout=timeout_per_source
                )

                if response.is_success:
                    data = response.json()
                    content = data.get("data", {}).get("markdown", "")
                    return (url, content)
                else:
                    logger.debug(f"[ExportGenerator] Source fetch failed for {url}: {response.status_code}")
                    return (url, "")

            except asyncio.TimeoutError:
                logger.debug(f"[ExportGenerator] Source fetch timeout for {url}")
                return (url, "")
            except Exception as e:
                logger.debug(f"[ExportGenerator] Source fetch error for {url}: {e}")
                return (url, "")

        # Fetch all sources in parallel
        logger.info(f"[ExportGenerator] Fetching {len(urls)} source URLs for enrichment")
        results = await asyncio.gather(*[fetch_single(url) for url in urls[:10]])  # Cap at 10 sources

        # Filter out empty results and build dict
        content_map = {url: content for url, content in results if content}
        logger.info(f"[ExportGenerator] Successfully fetched {len(content_map)}/{len(urls)} sources")

        return content_map

    async def generate_export(
        self,
        units: list[dict],
        location_name: str,
        language: str = "en",
        enrich_sources: bool = True,
        custom_system_prompt: str | None = None
    ) -> dict:
        """
        Generate article draft from atomic information units.

        Args:
            units: List of dicts with statement, unit_type, entities, source_url, source_domain
            location_name: Display name of the location
            language: Output language code (e.g., "en", "de", "fr")
            enrich_sources: Whether to re-fetch source URLs for additional context

        Returns:
            {
                "title": str,
                "headline": str,
                "sections": list[dict],  # {heading: str, content: str}
                "bullet_points": list[str],  # For backward compat
                "sources": list[dict]  # {title, url, domain}
            }
        """
        # Format units grouped by type
        units_text = self._format_units_by_type(units)

        # Analyze entities for coherent coverage
        frequent_entities = self._analyze_entities(units)
        topics = self._get_topics(units)

        # On-demand source enrichment: fetch full article content
        source_context = ""
        if enrich_sources:
            # Filter URLs for SSRF protection
            unique_urls = [
                url for url in {u.get("source_url") for u in units if u.get("source_url")}
                if self._is_safe_source_url(url)
            ]
            if unique_urls:
                source_contents = await self._fetch_source_content(unique_urls)
                if source_contents:
                    # Build source context section (cap each at 8K chars)
                    context_parts = []
                    for url, content in source_contents.items():
                        domain = urlparse(url).netloc
                        truncated = content[:8000]
                        context_parts.append(f"[Source: {domain}]\n{truncated}")
                    source_context = "\n\n---\n\n".join(context_parts)

        # Build the system prompt with fixed guardrails + optional user customization
        system_prompt = """You are a journalist's assistant using SMART BREVITY style. Generate a structured working draft from atomic information units. This is NOT a publishable article — it's a rough draft to accelerate a journalist's work.

Each unit is a verified, factual statement. Units are grouped by type:
- FACTS: Verifiable statements with specific data
- EVENTS: Things that happened or will happen
- ENTITY UPDATES: Changes in status of people, organizations, or places

CRITICAL - GROUNDING RULES (IMMUTABLE):
- Only use the provided units - NO hallucination
- NEVER add facts, quotes, dates, or statistics not present in the units or source content
- If information is missing, list it in 'gaps' — do NOT fill in with assumptions
- Every claim in the draft must be traceable to a specific unit or source

CRITICAL - HANDLING MULTIPLE TOPICS (IMMUTABLE):
- If units share entities, topics, or themes: group them into cohesive sections
- If units are UNRELATED: organize into SEPARATE DISTINCT sections with clear headings
- NEVER invent connections or imply relationships between facts that don't exist
- NEVER use transitional phrases like "Meanwhile" or "In related news" for unrelated topics
- Each section should stand alone — a reader should understand it without the other sections

"""

        # Add user-customizable writing guidelines (can be overridden)
        default_writing_guidelines = """WRITING GUIDELINES:
- Lead EVERY section with the most important fact — no throat-clearing or setup
- First sentence of each section = the news. Context comes after.
- Bold **key numbers, names, dates, and data** using markdown
- Sentences: SHORT and PUNCHY. Max 15-20 words per sentence.
- Paragraphs: 2-3 sentences max. One idea per paragraph.
- ALWAYS start bullet points with emojis: 📊 (data) 📅 (dates) 👤 (people) 🏢 (orgs) ⚠️ (concerns) ✅ (progress) 📍 (locations)
- Example: '📊 **42%** increase in housing costs [srf.ch]'
- Cite sources inline using [source.com] format
- Multi-source facts are more credible - mention when available
- Include a "gaps" list: what's missing, who to interview, data to verify
- Prioritize: numbers > dates > quotes > general statements"""

        # Use custom writing guidelines if provided, otherwise use defaults
        if custom_system_prompt:
            system_prompt += f"{custom_system_prompt}\n\n"
        else:
            system_prompt += f"{default_writing_guidelines}\n\n"

        system_prompt += """HEADLINE: One sentence capturing THE most newsworthy angle. Start with impact, not attribution.
SECTIONS: Each section heading should be 2-4 words. Content leads with the news, then context.

"""
        # Add language instruction if not English
        if language != "en":
            language_name = LANGUAGE_NAMES.get(language, language)
            system_prompt += f"""
IMPORTANT: Write the entire article in {language_name}. All text (title, headline, sections) must be in {language_name}.
"""

        system_prompt += """Output JSON format:
{
  "title": "Article title",
  "headline": "One-sentence lede summarizing the most newsworthy angle",
  "sections": [
    {
      "heading": "Section heading grouping related facts",
      "content": "📊 **Key stat** explains the news [source.com]. 📅 The deadline is..."
    }
  ],
  "gaps": ["What's missing or needs verification", "Who should be interviewed", "Data still needed"]
}"""

        # Build entity context section
        entity_context = ""
        if frequent_entities:
            entity_context = f"\n\nKEY ENTITIES (appear in multiple units): {', '.join(frequent_entities)}"

        topic_context = ""
        if topics:
            topic_context = f"\n\nTOPICS: {', '.join(topics)}"

        # Build source content section for enriched context
        source_section = ""
        if source_context:
            source_section = f"""

SOURCE CONTENT (for additional context - use to fill gaps in the units):
{source_context[:30000]}"""  # Cap total source content

        user_prompt = f"""Location: {location_name}

Information Units:
{units_text}{entity_context}{topic_context}{source_section}

Generate an article draft combining these units. Group related facts together.
Use the source content to find additional details (quotes, dates, context) that may be missing from the atomic units."""

        logger.info(f"[ExportGenerator] Generating draft from {len(units)} atomic units for {location_name}")

        client = await get_http_client()
        response = await client.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "HTTP-Referer": "https://cojournalist.ai",
                "X-Title": "coJournalist",
                "Content-Type": "application/json"
            },
            json={
                "model": self.MODEL,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                "max_tokens": self.MAX_TOKENS,
                "temperature": self.TEMPERATURE,
                "response_format": {"type": "json_object"}
            }
        )
        response.raise_for_status()
        data = response.json()

        # Parse response
        content = data["choices"][0]["message"]["content"]
        result = json.loads(content)

        # Build comprehensive sources list
        sources = []
        seen_urls = set()
        for u in units:
            # Primary source
            url = u.get("source_url")
            if url and url not in seen_urls:
                sources.append({
                    "title": u.get("source_title", ""),
                    "url": url,
                    "domain": u.get("source_domain", "")
                })
                seen_urls.add(url)

            # Additional sources (from merged duplicates)
            for additional in u.get("additional_sources", []):
                add_url = additional.get("url")
                if add_url and add_url not in seen_urls:
                    sources.append({
                        "title": additional.get("title", ""),
                        "url": add_url,
                        "domain": additional.get("domain", "")
                    })
                    seen_urls.add(add_url)

        result["sources"] = sources

        # Ensure backward compatibility
        result["bullet_points"] = []
        if "sections" not in result:
            result["sections"] = []
        if "gaps" not in result:
            result["gaps"] = []

        logger.info(f"[ExportGenerator] Generated draft: {result.get('title', 'No title')} with {len(sources)} sources")

        return result

    async def auto_select_units(
        self,
        units: list[dict],
        prompt: str,
        location: str | None = None,
        topic: str | None = None,
    ) -> dict:
        """
        Use LLM to auto-select the most relevant information units based on user criteria.

        Args:
            units: List of dicts with unit_id, statement, entities, created_at, date, etc.
            prompt: User's selection criteria (e.g. "Find articles about housing policy")
            location: Optional location filter context
            topic: Optional topic filter context

        Returns:
            {"selected_unit_ids": [...], "selection_summary": "..."}
        """
        from datetime import datetime, timezone

        current_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        # Format units for the prompt
        units_lines = []
        valid_ids = set()
        for u in units:
            uid = u.get("unit_id", "")
            valid_ids.add(uid)

            statement = u.get("statement", "")
            entities = u.get("entities", [])
            created_at = u.get("created_at", "")
            date_val = u.get("date")
            unit_type = u.get("unit_type", "fact")
            source = u.get("source_title", "")

            date_info = f", event_date: {date_val}" if date_val else ""
            entities_str = f", entities: {', '.join(entities[:5])}" if entities else ""

            units_lines.append(
                f"- id: {uid} | type: {unit_type} | created: {created_at}{date_info}{entities_str} | source: {source}\n  \"{statement}\""
            )

        units_text = "\n".join(units_lines)

        context_parts = []
        if location:
            context_parts.append(f"Location: {location}")
        if topic:
            context_parts.append(f"Topic: {topic}")
        context_str = "\n".join(context_parts) if context_parts else "No specific location or topic filter."

        system_prompt = f"""You are a journalist's assistant. Your job is to select the most relevant information units based on a user's criteria.

Current date: {current_date}

RULES:
- Only return unit IDs from the provided list
- Evaluate each unit against the selection criteria
- For recency criteria: consider both created_at timestamps and any dates mentioned in statements
- If date is provided, use it as the primary date signal
- If date is null, infer dates from the statement text and created_at timestamp
- Be inclusive rather than exclusive — when in doubt, include the unit
- Return an empty list if no units match the criteria

Output JSON:
{{"selected_unit_ids": ["id1", "id2", ...], "selection_summary": "Brief description of what was selected and why"}}"""

        user_prompt = f"""{context_str}

Selection criteria: {prompt}

Units to evaluate:
{units_text}

Select the units that match the criteria. Return JSON."""

        logger.info(f"[ExportGenerator] Auto-selecting from {len(units)} units")

        client = await get_http_client()
        response = await client.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "HTTP-Referer": "https://cojournalist.ai",
                "X-Title": "coJournalist",
                "Content-Type": "application/json"
            },
            json={
                "model": self.MODEL,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                "max_tokens": 1000,
                "temperature": 0.1,
                "response_format": {"type": "json_object"}
            }
        )
        response.raise_for_status()
        data = response.json()

        content = data["choices"][0]["message"]["content"]
        result = json.loads(content)

        # Filter out any hallucinated IDs
        selected_ids = [uid for uid in result.get("selected_unit_ids", []) if uid in valid_ids]

        return {
            "selected_unit_ids": selected_ids,
            "selection_summary": result.get("selection_summary", f"{len(selected_ids)} units selected"),
        }
