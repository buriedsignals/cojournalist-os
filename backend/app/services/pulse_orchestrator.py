"""
PulseOrchestrator — Smart Scout (type pulse) orchestration.

PURPOSE: Execute the full search-to-filtered-results pipeline for Smart Scouts.
Handles multi-language query generation, Firecrawl search, date filtering,
embedding-based deduplication, cluster analysis, and AI relevance filtering.

DEPENDS ON: config (API keys), news_utils (FirecrawlTools, dedup, AI filter,
    date parsing, summary, is_index_or_homepage, is_likely_standing_page,
    is_likely_tourism_content, enrich_pdf_results), query_generator (LLM query generation)
USED BY: routers/pulse.py

Pipeline flow (search_news):
  1. Query generation — LLM generates search queries for the location/topic
  2. Search execution — Firecrawl API returns raw results (news + web sources)
     Homepage/index and standing pages are rejected during URL dedup
     (is_index_or_homepage, is_likely_standing_page).
  2.5. Cross-category URL exclusion — optional exclude_urls param for UI dedup
  2.6. PDF OCR enrichment — scrapes PDF URLs via Firecrawl to extract text,
     dates, and descriptions (capped at 3 PDFs per search)
  3. Date filter — removes articles older than scope-aware cutoff windows
     AND a 90-day absolute staleness floor (ABSOLUTE_STALENESS_DAYS)
  4. Undated cap — limits undated articles per bucket (news vs discovery)
  4.5. Tourism pre-filter — removes tourism/travel content before dedup
     to prevent inflating cluster sizes of legitimate articles.
  5. Embedding dedup — clusters similar articles, picks best per cluster
  6. Cluster filter (niche only) — drops mainstream news (cluster_size >= 3
     for news, >= 5 for discovery articles)
  7. AI filter — LLM selects the most relevant articles for the journalist
  8. Domain cap — limits per-domain results (inside ai_filter_results);
     reliable mode gets domain_cap=3, niche gets domain_cap=2

Two source modes:
  - niche: news + web sources, LLM-generated discovery queries, cluster
    filtering, tourism heuristic. Surfaces community blogs, local forums,
    and under-reported stories.
  - reliable: news-only sources, no discovery pass. Wider date windows (21d
    for location) and higher AI filter target (6-8) for comprehensive
    coverage from trusted outlets.
"""
import asyncio
import logging
import time
from datetime import datetime, timedelta
from typing import Optional, List, Literal
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

from app.config import settings
from app.services.news_utils import (
    FirecrawlTools,
    AINewsArticle,
    AgentResponse,
    get_country_code,
    CODE_TO_COUNTRY_NAME,
    parse_published_date,
    normalize_date_to_iso,
    deduplicate_by_embedding,
    generate_news_summary,
    ai_filter_results,
    is_index_or_homepage,
    is_likely_standing_page,
    is_likely_tourism_content,
    is_stale_content,
    enrich_pdf_results,
)
from app.services.query_generator import get_query_generator

# Maximum concurrent Firecrawl search requests. Controls parallelism to
# stay within API rate limits while still being much faster than sequential.
MAX_CONCURRENT_SEARCHES = 5


def get_recency_config(scope: str, category: str, source_mode: str = "niche") -> dict:
    """Return date windows and undated caps based on search scope, category, and source mode.

    The pulse pipeline filters raw search results by publication date before
    AI filtering. These windows control how far back we look. Wider windows
    mean more candidates reach the AI filter, which is especially important
    for reliable mode (news-only sources that always have dates — the undated
    cap barely helps, so the date window is the sole volume knob).

    Scope (location vs topic):
      - Location: tight windows — weekly beat coverage for a geographic area.
      - Topic: wider windows — specific criteria + dedup prevents repeat surfacing.

    Source mode (niche vs reliable):
      - Niche: includes web/blog sources that lag behind news; discovery pass
        gets a slightly wider window than news pass.
      - Reliable: news-only sources from established outlets. Wider windows
        ensure enough dated articles survive to give the AI filter real
        editorial choices. Reliable should be MORE consistent than niche.

    Government category: uses generous undated caps (25) since gov sites
    legitimately lack publication dates, but still finite to filter old PDFs.
    """
    RECENCY_CONFIG = {
        # All scope/mode combos use a standard 14-day window.
        # Relaxation extends to 28 days when 0 dated results survive.
        ("location", "niche"): {
            "news_days": 14,
            "discovery_days": 14,
            "max_undated_news": 10,
            "max_undated_discovery": 10,
        },
        ("location", "reliable"): {
            "news_days": 14,
            "discovery_days": 14,
            "max_undated_news": 15,
            "max_undated_discovery": 15,
        },
        ("topic", "niche"): {
            "news_days": 14,
            "discovery_days": 14,
            "max_undated_news": 20,
            "max_undated_discovery": 20,
        },
        ("topic", "reliable"): {
            "news_days": 14,
            "discovery_days": 14,
            "max_undated_news": 25,
            "max_undated_discovery": 25,
        },
        ("combined", "niche"): {
            "news_days": 14,
            "discovery_days": 14,
            "max_undated_news": 15,
            "max_undated_discovery": 15,
        },
        ("combined", "reliable"): {
            "news_days": 14,
            "discovery_days": 14,
            "max_undated_news": 20,
            "max_undated_discovery": 20,
        },
    }

    config = RECENCY_CONFIG.get(
        (scope, source_mode),
        RECENCY_CONFIG[("location", "niche")]  # Conservative fallback
    )

    if category == "government":
        return {**config, "max_undated_news": 25, "max_undated_discovery": 25}
    return config


def apply_date_filter(
    results: List[dict],
    recency: dict,
    absolute_staleness_days: int = 90,
) -> tuple:
    """Filter results by publication date with progressive relaxation.

    Returns (dated_results, undated_results).

    If all dated articles are too old for the initial window but some fall
    within a 2x-relaxed window (capped at absolute_staleness_days), those
    are recovered rather than returning 0 dated results.
    """
    cutoff_news = datetime.now() - timedelta(days=recency["news_days"])
    cutoff_discovery = datetime.now() - timedelta(days=recency["discovery_days"])
    absolute_cutoff = datetime.now() - timedelta(days=absolute_staleness_days)

    dated_results = []
    undated_results = []
    for item in results:
        pub_date = parse_published_date(item.get("date"))
        is_discovery = item.get("_pass") == "discovery"
        cutoff = cutoff_discovery if is_discovery else cutoff_news
        if pub_date:
            if pub_date >= cutoff and pub_date >= absolute_cutoff:
                dated_results.append(item)
        else:
            undated_results.append(item)

    # Progressive date relaxation: if ALL dated articles were too old,
    # try a fixed 28-day fallback window (capped at absolute_staleness_days)
    RELAXED_WINDOW_DAYS = 28

    if not dated_results:
        rejected_dated_count = sum(
            1 for item in results
            if parse_published_date(item.get("date"))
        )
        if rejected_dated_count > 0:
            relaxed_days = min(RELAXED_WINDOW_DAYS, absolute_staleness_days)
            relaxed_cutoff = datetime.now() - timedelta(days=relaxed_days)

            for item in results:
                pub_date = parse_published_date(item.get("date"))
                if not pub_date:
                    continue
                if pub_date >= relaxed_cutoff and pub_date >= absolute_cutoff:
                    dated_results.append(item)

            if dated_results:
                logger.info(
                    f"Date relaxation: recovered {len(dated_results)} articles "
                    f"with {relaxed_days}d window (was {recency['news_days']}d)"
                )

    return dated_results, undated_results


def cap_undated_results(
    undated_results: List[dict],
    max_undated: int = 10,
    max_undated_discovery: int = 10,
    category: str = "news",
) -> List[dict]:
    """Cap undated results using a two-bucket approach: news vs discovery.

    Web/blog content (discovery pass) often lacks publication dates, so it
    gets a separate cap from news. Without this, undated discovery articles
    would compete for the same slots as undated news articles and get crowded
    out. Government category uses generous caps (25) from recency config
    but still respects limits to filter old undated PDFs.

    Args:
        undated_results: Articles that had no parseable publication date.
        max_undated: Cap for news-pass undated articles.
        max_undated_discovery: Cap for discovery-pass undated articles.
        category: Category name (all categories respect caps).
    """
    discovery_undated = [r for r in undated_results if r.get("_pass") == "discovery"]
    other_undated = [r for r in undated_results if r.get("_pass") != "discovery"]
    capped_other = other_undated[:max_undated]
    capped_discovery = discovery_undated[:max_undated_discovery]
    if len(other_undated) > max_undated:
        logger.info(f"Capped news undated from {len(other_undated)} to {max_undated}")
    if len(discovery_undated) > max_undated_discovery:
        logger.info(f"Capped discovery undated from {len(discovery_undated)} to {max_undated_discovery}")
    return capped_other + capped_discovery


def filter_by_date(article: dict, news_days: int = 7, discovery_days: int = 14) -> bool:
    """Check if a single article passes the date filter (standalone helper).

    Used by tests and standalone filtering. The main search_news() pipeline
    uses an inline loop with the same logic but scope-aware windows from
    get_recency_config(). Defaults match the most conservative config
    (location/niche: 7-day news, 14-day discovery).

    Articles without dates always pass — they're handled separately by the
    undated cap in cap_undated_results().
    """
    pub_date = parse_published_date(article.get("date"))
    if not pub_date:
        return True  # Undated articles pass; capped separately

    is_discovery = article.get("_pass") == "discovery"
    cutoff = datetime.now() - timedelta(days=discovery_days if is_discovery else news_days)
    return pub_date >= cutoff


class PulseOrchestrator:
    """
    Smart Scout (type pulse) orchestration.
    Executes direct searches, deduplicates, filters, and generates summaries.
    """

    def __init__(self):
        self.openrouter_key = settings.openrouter_api_key
        self.firecrawl_key = settings.firecrawl_api_key
        self.tools = FirecrawlTools(self.firecrawl_key)

    async def _execute_all_searches_directly(
        self,
        queries: List[dict],
        location: Optional[str] = None,
        country_code: Optional[str] = None,
        limit_per_query: int = 25,
        lang: Optional[str] = None,
    ) -> tuple[List[dict], List[str]]:
        """
        Execute all search queries concurrently against Firecrawl API.

        Uses a semaphore to limit concurrency to MAX_CONCURRENT_SEARCHES,
        preventing API rate limit errors while executing much faster than
        sequential iteration.

        Args:
            queries: List of dicts, each with "query", "sources", and "_pass" keys.
            location: Geo-targeting location string.
            country_code: ISO country code.
            limit_per_query: Max results per query.
            lang: Language hint for non-English searches.

        Returns:
            Tuple of (combined_results, executed_queries)
        """
        if not queries:
            return [], []

        logger.info(f"Executing {len(queries)} queries concurrently (max {MAX_CONCURRENT_SEARCHES} parallel)...")

        semaphore = asyncio.Semaphore(MAX_CONCURRENT_SEARCHES)

        async def _search_one(query_item: dict) -> tuple[str, list[dict]]:
            """Execute a single search query with semaphore-controlled concurrency."""
            query_str = query_item["query"]
            sources = query_item.get("sources", ["news", "web"])
            pass_type = query_item.get("_pass", "news")

            # Remove quotes for the actual search
            clean_query = query_str.strip('"')

            async with semaphore:
                result = await self.tools.search_web(
                    query=clean_query,
                    location=location,
                    country=country_code,
                    limit=limit_per_query,
                    sources=sources,
                    lang=lang,
                )

            # Tag results with pass type
            items = []
            if "results" in result:
                for item in result["results"]:
                    item["_pass"] = pass_type
                    items.append(item)

            return clean_query, items

        # Execute all searches concurrently
        search_results = await asyncio.gather(
            *[_search_one(q) for q in queries],
            return_exceptions=True,
        )

        # Collect results, deduplicating by URL
        all_results = []
        executed_queries = []
        seen_urls = set()

        for result in search_results:
            if isinstance(result, Exception):
                logger.warning(f"Search query failed: {result}")
                continue

            clean_query, items = result
            executed_queries.append(clean_query)

            for item in items:
                url = item.get("url", "")
                if not url or url in seen_urls:
                    continue
                if is_index_or_homepage(url) or is_likely_standing_page(url):
                    continue
                seen_urls.add(url)
                all_results.append(item)

        logger.info(f"Found {len(all_results)} unique results from {len(executed_queries)} queries")
        return all_results, executed_queries

    async def search_news(
        self,
        location: Optional[str] = None,
        city: Optional[str] = None,
        country: Optional[str] = None,
        category: Literal["news", "government", "analysis"] = "news",
        custom_filter_prompt: Optional[str] = None,
        recent_findings: Optional[List[dict]] = None,
        language: str = "en",
        excluded_domains: Optional[List[str]] = None,
        source_mode: Literal["reliable", "niche"] = "niche",
        criteria: Optional[str] = None,
        exclude_urls: Optional[List[str]] = None,
        priority_sources: Optional[List[str]] = None,
    ) -> AgentResponse:
        """Execute Smart Scout (type pulse) search — the main pipeline entry point.

        Scope modes (determined by which of location/topic are provided):
          - Location-only: geo-targeted local news
          - Topic-only: global topic search without geo-targeting
          - Combined: both location and topic (config exists but frontend
            currently prevents this combination in discovery mode)

        Source modes (controls source diversity and filtering aggressiveness):
          - niche: news + web sources, discovery pass for blogs/forums,
            cluster filtering drops mainstream news. Target: 6 articles.
          - reliable: news-only sources from established outlets, wider date
            windows, no discovery pass or cluster filter. Target: 8 articles.

        Category affects query generation and AI filter prompts:
          - "news": standard news + discovery queries
          - "government": adds institutional/gov web queries, bypasses undated caps
          - "analysis": opinion/blog/deep-dive queries (topic-only)

        See module docstring for the full pipeline stage breakdown.
        """
        start_time = time.time()

        # Track search queries
        search_queries: List[str] = []

        # Get country code for local language queries
        country_code = get_country_code(country) if country else None
        logger.info(f"Location: {location}, Country: {country}, Code: {country_code}, Category: {category}, Criteria: {criteria}")

        # Determine search mode
        has_location = bool(city or country or location)
        has_criteria = bool(criteria)

        # --- Pipeline stages 1-2: Query generation + search execution ---
        # Two branches: location-based (LLM generates local queries) vs
        # topic-only (hardcoded query templates, no geo-targeting).

        if has_location:
            # Location-based mode: LLM generates local queries
            # Use city if available; do NOT derive city from location string
            # (location may be a country name like "Sweden", not a city)
            city_name = city if city else ""
            display_name = city or location or criteria  # For logging/summary only

            query_gen = get_query_generator()
            local_query_result = await query_gen.generate_queries(
                city=city_name or (location.split(",")[0].strip() if location and "," in location else ""),
                country_code=country_code or "",
                num_queries=7,
                category=category,
                criteria=criteria,
            )

            local_domains = local_query_result.get("local_domains", [])
            tld = next((d for d in local_domains if d.startswith(".")), None) if local_domains else None
            languages = local_query_result.get("languages", [local_query_result.get("language", "en")])
            primary_lang = languages[0] if languages else "en"

            # Build tagged query list
            # search_label: best available name for the location in search queries
            search_label = city_name or (location.split(",")[0].strip() if location else "") or country_code or ""
            all_queries = []
            query_sources = ["news"] if source_mode == "reliable" else ["news", "web"]

            # News queries from LLM
            for q in local_query_result.get("queries", []):
                all_queries.append({"query": f'"{q}"', "sources": query_sources, "_pass": "news"})

            # TLD query (only if we have a label to search for)
            if tld and search_label:
                all_queries.append({"query": f'site:*{tld} "{search_label}"', "sources": query_sources, "_pass": "news"})

            # Criteria + location combined queries
            if has_criteria:
                combo_queries = []
                if search_label and country:
                    # Combine city + country for disambiguation without national drift
                    # e.g., "housing" "London" GB — distinguishes London UK from London CA
                    combo_queries.append({"query": f'"{criteria}" "{search_label}" {country}', "sources": query_sources, "_pass": "news"})
                elif search_label:
                    combo_queries.append({"query": f'"{criteria}" "{search_label}"', "sources": query_sources, "_pass": "news"})
                else:
                    # Country-only scope (no city) — country query is appropriate
                    combo_queries.append({"query": f'"{criteria}" {country or ""}', "sources": query_sources, "_pass": "news"})
                all_queries.extend(combo_queries)

            # Discovery queries (web-only, non-news content) — LLM-generated for news/niche
            if category == "news" and source_mode == "niche":
                for q in local_query_result.get("discovery_queries", []):
                    all_queries.append({"query": f'"{q}"', "sources": ["web"], "_pass": "discovery"})

            # Government/institutional discovery queries from LLM (web-only, public sector sites)
            if category == "government":
                for q in local_query_result.get("discovery_queries", []):
                    all_queries.append({"query": f'"{q}"', "sources": ["web"], "_pass": "government"})

            local_count = len(local_query_result.get("queries", []))
            cached = local_query_result.get("cached", False)
            fallback = local_query_result.get("fallback", False)
            # Append site-specific queries for priority sources
            if priority_sources:
                search_label = city_name or criteria or ""
                for domain in priority_sources[:5]:
                    all_queries.append({"query": f'site:{domain} "{search_label}"', "sources": ["web"], "_pass": "news"})
                logger.info(f"Added {min(len(priority_sources), 5)} priority source queries")

            logger.info(f"Generated {len(all_queries)} queries for {display_name}: {local_count} local (languages: {languages}), cached={cached}, fallback={fallback}")

            # Execute searches with geo-targeting and language hint
            pre_fetched_results, search_queries = await self._execute_all_searches_directly(
                queries=all_queries,
                location=city or (location.split(",")[0].strip() if location else None),
                country_code=country_code,
                limit_per_query=25,
                lang=primary_lang if primary_lang != "en" else None,  # Only pass non-English languages
            )

            local_tlds = local_query_result.get("local_domains", [])
            local_language = primary_lang  # Use detected primary language (e.g., "fr" for Montreal)
            filter_city = city_name or (location.split(",")[0].strip() if location else "")
            filter_country = CODE_TO_COUNTRY_NAME.get(country_code, "") or location or country or "Unknown"

        else:
            # Criteria-only mode: no geo-targeting
            # Detect if criteria references a specific country for multi-language search
            from app.services.query_generator import detect_topic_country
            topic_country = await detect_topic_country(criteria, api_key=self.openrouter_key)

            query_sources = ["news"] if source_mode == "reliable" else ["news", "web"]
            if category == "analysis":
                topic_queries = [
                    {"query": f'"{criteria}" blog', "sources": query_sources, "_pass": "news"},
                    {"query": f'"{criteria}" analysis', "sources": query_sources, "_pass": "news"},
                    {"query": f'"{criteria}" opinion', "sources": query_sources, "_pass": "news"},
                    {"query": f'"{criteria}" deep dive', "sources": query_sources, "_pass": "news"},
                    {"query": f'"{criteria}" research report', "sources": query_sources, "_pass": "news"},
                ]
            else:
                topic_queries = [
                    {"query": f'"{criteria}"', "sources": query_sources, "_pass": "news"},
                    {"query": f'"{criteria}" news', "sources": query_sources, "_pass": "news"},
                    {"query": f'"latest {criteria}"', "sources": query_sources, "_pass": "news"},
                    {"query": f'"{criteria}" update', "sources": query_sources, "_pass": "news"},
                    {"query": f'"{criteria}" report', "sources": query_sources, "_pass": "news"},
                ]

            # Append site-specific queries for priority sources
            if priority_sources:
                for domain in priority_sources[:5]:
                    topic_queries.append({"query": f'site:{domain} "{criteria}"', "sources": ["web"], "_pass": "news"})
                logger.info(f"Added {min(len(priority_sources), 5)} priority source queries")

            logger.info(f"Generated {len(topic_queries)} criteria-only queries for: {criteria}")

            # Execute searches — with dual-language if a country was detected
            if topic_country and topic_country[1] != language:
                local_lang = topic_country[1]
                logger.info(f"Topic references {topic_country[0]} — searching in both {local_lang} and {language}")

                # Run both language searches concurrently
                (results_user_lang, queries_user), (results_local_lang, queries_local) = await asyncio.gather(
                    self._execute_all_searches_directly(
                        queries=topic_queries,
                        location=None,
                        country_code=topic_country[0],
                        limit_per_query=25,
                        lang=language if language != "en" else None,
                    ),
                    self._execute_all_searches_directly(
                        queries=topic_queries,
                        location=None,
                        country_code=topic_country[0],
                        limit_per_query=25,
                        lang=local_lang,
                    ),
                )

                # Merge results (URL-dedup)
                seen_urls = {r.get("url") for r in results_user_lang}
                for r in results_local_lang:
                    if r.get("url") not in seen_urls:
                        results_user_lang.append(r)
                        seen_urls.add(r.get("url"))

                pre_fetched_results = results_user_lang
                search_queries = queries_user + queries_local
                local_language = local_lang  # Set local language for dedup scoring
            else:
                pre_fetched_results, search_queries = await self._execute_all_searches_directly(
                    queries=topic_queries,
                    location=None,
                    country_code=topic_country[0] if topic_country else None,
                    limit_per_query=25,
                    lang=language if language != "en" else None,
                )
                local_language = None

            local_tlds = []
            city_name = criteria
            filter_city = ""
            filter_country = ""

        # --- Pipeline stage 2.5: Cross-category URL exclusion ---
        if exclude_urls:
            exclude_set = set(exclude_urls)
            pre_fetched_results = [r for r in pre_fetched_results if r.get("url") not in exclude_set]

        # --- Pipeline stage 2.6: PDF OCR enrichment ---
        # Scrape PDF URLs to extract text, dates, and better descriptions.
        # This runs before date filtering so extracted dates can be used.
        pre_fetched_results = await enrich_pdf_results(
            results=pre_fetched_results,
            firecrawl_tools=self.tools,
        )

        # --- Pipeline stage 3: Date filter + undated cap ---
        # Scope determines date windows; source_mode widens them for reliable.
        scope = "combined" if (has_criteria and has_location) else ("topic" if has_criteria else "location")
        recency = get_recency_config(scope, category, source_mode=source_mode)

        # Filter by date using scope-aware windows + absolute staleness floor
        ABSOLUTE_STALENESS_DAYS = 90
        dated_results, undated_results = apply_date_filter(
            pre_fetched_results, recency, ABSOLUTE_STALENESS_DAYS
        )

        # Content staleness filter for undated articles
        pre_stale = len(undated_results)
        undated_results = [
            item for item in undated_results
            if not is_stale_content(
                url=item.get("url", ""),
                title=item.get("title", ""),
                max_age_years=1
            )
        ]
        stale_dropped = pre_stale - len(undated_results)
        if stale_dropped:
            logger.info(f"Content staleness filter dropped {stale_dropped} undated articles with old year references")

        # Cap undated results using scope-aware caps
        capped_undated = cap_undated_results(
            undated_results,
            max_undated=recency["max_undated_news"],
            max_undated_discovery=recency["max_undated_discovery"],
            category=category,
        )
        filtered_results = dated_results + capped_undated

        logger.info(f"Filtered to {len(dated_results)} dated + {len(undated_results)} undated results")

        # Tourism content pre-filter (before embedding dedup to prevent
        # tourism articles from distorting cluster sizes)
        if category == "news" and source_mode == "niche" and has_location:
            pre_tourism = len(filtered_results)
            filtered_results = [a for a in filtered_results if not is_likely_tourism_content(a)]
            tourism_dropped = pre_tourism - len(filtered_results)
            if tourism_dropped:
                logger.info(f"Tourism pre-filter dropped {tourism_dropped} travel/tourism articles")

        # --- Pipeline stage 5: Embedding dedup ---
        # Clusters similar articles and picks the best per cluster using
        # rarity scoring (language-aware for non-English locales).
        # Scope-aware dedup threshold: narrower search spaces need higher
        # thresholds to avoid merging distinct stories that share vocabulary.
        if has_criteria and has_location:
            dedup_threshold = 0.85  # Combined: narrow search space
        elif has_location:
            dedup_threshold = 0.82  # Location-only: moderate
        else:
            dedup_threshold = 0.80  # Criteria-only: diverse results

        deduplicated = await deduplicate_by_embedding(
            articles=filtered_results,
            threshold=dedup_threshold,
            local_tlds=local_tlds,
            primary_language=local_language
        )

        logger.info(f"Deduplicated to {len(deduplicated)} unique articles from {len(filtered_results)}")

        # --- Pipeline stage 6: Cluster filter (niche only) ---
        # In niche mode, drops mainstream news (cluster_size >= 3) to surface
        # under-reported stories. Reliable mode skips this — all deduplicated
        # articles from trusted sources are valuable.
        if category == "news" and source_mode == "niche":
            # Discovery: higher threshold (5+) — these are the target content,
            # but cross-pass mainstream coverage should still be caught.
            niche_pool = [a for a in deduplicated if a.get("_pass") == "discovery" and a.get("_cluster_size", 1) <= 4]
            # News + other: standard threshold (3+) — mainstream stories the journalist already knows.
            news_pool = [a for a in deduplicated if a.get("_pass") != "discovery" and a.get("_cluster_size", 1) <= 2]
            discovery_candidates = niche_pool + news_pool
            mainstream_dropped = len(deduplicated) - len(discovery_candidates)
            if mainstream_dropped:
                logger.info(f"Cluster filter dropped {mainstream_dropped} mainstream articles")
            logger.info(f"Discovery candidates: {len(niche_pool)} niche + {len(news_pool)} news = {len(discovery_candidates)}")
        else:
            discovery_candidates = deduplicated

        # --- Pipeline stage 7: AI filter ---
        filter_prompt = custom_filter_prompt or ""
        if recent_findings:
            exclusions = "; ".join(f.get("summary_text", "") for f in recent_findings if f.get("summary_text"))
            if exclusions:
                filter_prompt += f"\n\nRECENT PREVIOUS FINDINGS (skip these topics, they were already reported): {exclusions}"

        # Reliable sources are pre-vetted (established newspapers, broadcasters).
        # More results is better — the journalist wants comprehensive coverage
        # from trusted sources, not just the top 6.
        target_results = 8 if source_mode == "reliable" else 6
        ai_filtered = await ai_filter_results(
            results=discovery_candidates,
            city_name=filter_city,
            country_name=filter_country,
            openrouter_key=self.openrouter_key,
            max_results=target_results,
            local_language=local_language,
            category=category,
            custom_filter_prompt=filter_prompt if filter_prompt.strip() else None,
            topic=criteria,
            excluded_domains=excluded_domains,
            source_mode=source_mode,
            criteria=criteria,
            priority_sources=priority_sources,
        )

        filtered_out_count = len(discovery_candidates) - len(ai_filtered)
        logger.info(f"AI filtered to {len(ai_filtered)} relevant articles ({filtered_out_count} filtered out)")

        # --- Pipeline stage 8: Convert to response objects ---
        articles = []
        for item in ai_filtered:
            url = item.get("url", "")
            try:
                source = urlparse(url).netloc.replace("www.", "")
            except Exception:
                source = "Unknown"

            articles.append(AINewsArticle(
                title=item.get("title", "Untitled"),
                url=url,
                source=source,
                summary=item.get("description", "")[:300],
                date=normalize_date_to_iso(item.get("date")),
                imageUrl=item.get("favicon"),
                verified=False
            ))

        # Generate summary
        summary_label = (display_name if has_location else city_name) or ""
        news_summary = await generate_news_summary(
            articles=ai_filtered,
            city=summary_label,
            api_key=self.openrouter_key,
            category=category,
            language=language
        )

        processing_time = int((time.time() - start_time) * 1000)

        logger.info(f"Returning {len(articles)} articles in {processing_time}ms")

        return AgentResponse(
            status="completed",
            mode="pulse",
            category=category,
            task_completed=True,
            response_markdown="",
            articles=articles,
            total_results=len(pre_fetched_results),
            search_queries_used=search_queries,
            urls_scraped=[],
            processing_time_ms=processing_time,
            summary=news_summary,
            filtered_out_count=filtered_out_count,
        )
