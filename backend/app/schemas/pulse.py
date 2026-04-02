"""
Pydantic schemas for Pulse scout (Smart Scout) endpoints.

PURPOSE: Request/response models for POST /pulse/search (UI) and
POST /pulse/execute (Lambda). Includes input validation for scope
(location and/or criteria required), criteria sanitization, and
source mode selection.

DEPENDS ON: models/modes (ScoutMode), schemas/scouts (GeocodedLocation,
    SupportedLanguage), schemas/common (AINewsArticle)
USED BY: routers/pulse.py
"""
import re
from typing import List, Literal, Optional

from pydantic import BaseModel, Field, field_validator, model_validator

from app.models.modes import ScoutMode
from app.schemas.scouts import GeocodedLocation, SupportedLanguage
from app.schemas.common import AINewsArticle


# =============================================================================
# UI-Triggered Search Schemas (from news.py)
# =============================================================================

class PulseSearchRequest(BaseModel):
    """Request for UI-triggered pulse search."""
    location: Optional[GeocodedLocation] = Field(None, description="Location for geo-targeted search")
    category: Literal["news", "government", "analysis"] = Field("news", description="Category: 'news' for general, 'government' for municipal")
    custom_filter_prompt: Optional[str] = Field(None, max_length=2000, description="Custom AI filter prompt (overrides default)")
    source_mode: Literal["reliable", "niche"] = Field("niche", description="Source mode: reliable for established outlets, niche for community/underreported content")
    criteria: Optional[str] = Field(None, max_length=500, description="Search driver — what to search for (topic, keywords, or specific criteria)")
    excluded_domains: Optional[List[str]] = Field(None, max_length=50, description="Per-scout domain blacklist")
    exclude_urls: Optional[List[str]] = Field(default=None, description="URLs to exclude (cross-category dedup)")

    @field_validator('excluded_domains')
    @classmethod
    def sanitize_excluded_domains(cls, v: Optional[List[str]]) -> Optional[List[str]]:
        if v is None:
            return v
        cleaned = []
        for d in v[:50]:
            d = re.sub(r'^https?://', '', d).strip()
            d = re.sub(r'^www\.', '', d)
            d = re.sub(r'/.*$', '', d)
            if d and '.' in d:
                cleaned.append(d)
        return cleaned or None

    @model_validator(mode='after')
    def validate_location_or_criteria(self):
        if not self.location and not self.criteria:
            raise ValueError('At least one of location or criteria must be provided')
        return self

    class Config:
        json_schema_extra = {
            "example": {
                "location": {
                    "displayName": "Salzburg, Austria",
                    "city": "Salzburg",
                    "country": "AT",
                    "locationType": "city"
                },
                "criteria": "local politics",
                "category": "news",
                "custom_filter_prompt": None
            }
        }


class PulseSearchResponse(BaseModel):
    """
    Response from UI-triggered pulse search.
    Returns AI-curated local news articles.
    """
    status: Literal["completed", "partial", "not_found", "failed"] = Field(
        "completed",
        description="Search status"
    )
    mode: ScoutMode = Field(ScoutMode.PULSE, description="Search mode")
    category: Literal["news", "government", "analysis"] = Field("news", description="Search category")
    task_completed: bool = Field(False, description="Whether AI agent completed successfully")
    response_markdown: str = Field("", description="AI-generated markdown summary")
    articles: List[AINewsArticle] = Field(default_factory=list, description="List of verified articles")
    totalResults: int = Field(0, description="Number of articles returned")
    search_queries_used: List[str] = Field(default_factory=list, description="Search queries executed")
    urls_scraped: List[str] = Field(default_factory=list, description="URLs that were scraped")
    processing_time_ms: Optional[int] = Field(None, description="Processing time in milliseconds")
    summary: str = Field("", description="AI-generated summary for this category")
    filteredOutCount: int = Field(0, description="Number of articles filtered out by AI")
    error: Optional[str] = Field(None, description="Error message if search failed")


# =============================================================================
# Lambda-Triggered Execution Schemas (from scouts.py)
# =============================================================================

class PulseExecuteRequest(BaseModel):
    """Request for Lambda-triggered pulse scout execution."""
    location: Optional[GeocodedLocation] = None
    topic: Optional[str] = Field(None, max_length=200, description="Organizational tag for info unit tagging (from SCRAPER# record)")
    userId: str
    scraperName: str = Field(..., min_length=1, max_length=100)
    preferred_language: SupportedLanguage = Field("en", description="User preferred language code")
    skip_notification: bool = Field(False, description="Skip email notification (used for initial run)")
    skip_credit_charge: bool = Field(False, description="Skip credit deduction (used for initial run)")
    skip_unit_extraction: bool = Field(False, description="Skip unit extraction (used for initial run)")
    source_mode: Literal["reliable", "niche"] = Field("niche", description="Source mode: reliable or niche")
    criteria: Optional[str] = Field(None, max_length=500, description="Search driver — what to search for")
    excluded_domains: Optional[List[str]] = Field(None, max_length=50, description="Per-scout domain blacklist")

    @model_validator(mode='after')
    def backfill_criteria_from_topic(self):
        """Backward compat: old SCRAPER# records store search term in topic.
        If criteria is empty but topic is set, copy topic → criteria."""
        if not self.criteria and self.topic:
            self.criteria = self.topic
        return self

    @model_validator(mode='after')
    def validate_location_or_criteria(self):
        if not self.location and not self.criteria:
            raise ValueError('At least one of location or criteria must be provided')
        return self

    @field_validator('scraperName')
    @classmethod
    def sanitize_name(cls, v: str) -> str:
        # Remove characters that could cause issues in DynamoDB keys
        return re.sub(r'[#|]', '-', v).strip()


class PulseExecuteResponse(BaseModel):
    """Response from Lambda-triggered pulse scout execution."""
    scraper_status: bool = Field(..., description="True if search completed successfully")
    criteria_status: bool = Field(..., description="Always True for pulse (always notify)")
    summary: str = Field(..., description="AI-generated summary of news")
    articles_count: int = Field(..., description="Number of articles found")
    notification_sent: bool = Field(..., description="Whether email was sent")
