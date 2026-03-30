"""
Pydantic schemas for the v1 external API.

PURPOSE: Request/response models for all /api/v1/* endpoints:
- API key management (session cookie auth)
- Scout CRUD + run-now (API key auth)
- Information unit listing + semantic search (API key auth)

DEPENDS ON: schemas/scouts (GeocodedLocation), models/modes (RegularityType,
    MonitoringType, ScoutType)
USED BY: routers/v1.py
"""
from typing import Literal, Optional
from datetime import datetime

from pydantic import BaseModel, Field, model_validator

from app.schemas.scouts import GeocodedLocation
from app.models.modes import RegularityType, ScoutType


# =============================================================================
# API Keys
# =============================================================================


class CreateApiKeyRequest(BaseModel):
    """Request to create a new API key."""

    name: str = Field(default="", max_length=100, description="Human-readable label for the key")

    class Config:
        json_schema_extra = {
            "example": {
                "name": "My integration"
            }
        }


class ApiKeyResponse(BaseModel):
    """Response after creating an API key.

    The raw key is shown exactly once — it cannot be retrieved again.
    """

    key: str = Field(..., description="Raw API key (shown once — store securely)")
    key_id: str = Field(..., description="Stable identifier for the key")
    key_prefix: str = Field(..., description="First 7 characters of the key (safe to display)")
    name: str = Field(..., description="Human-readable label")
    created_at: str = Field(..., description="ISO 8601 creation timestamp (UTC)")


class ApiKeyListItem(BaseModel):
    """Metadata for a single API key (no raw key)."""

    key_id: str = Field(..., description="Stable identifier for the key")
    key_prefix: str = Field(..., description="First 7 characters of the key (safe to display)")
    name: str = Field(..., description="Human-readable label")
    created_at: str = Field(..., description="ISO 8601 creation timestamp (UTC)")
    last_used_at: Optional[str] = Field(None, description="ISO 8601 timestamp of last use (UTC)")


class ApiKeyListResponse(BaseModel):
    """Response listing all API keys for the authenticated user."""

    keys: list[ApiKeyListItem]
    count: int


# =============================================================================
# Scouts — shared sub-models
# =============================================================================


class ScheduleConfig(BaseModel):
    """Schedule configuration for a scout."""

    regularity: RegularityType = Field(..., description="Run frequency: daily, weekly, or monthly")
    time: str = Field(
        ...,
        pattern=r"^([0-1]?[0-9]|2[0-3]):[0-5][0-9]$",
        description="Run time in HH:MM format (UTC)",
    )
    day_number: int = Field(
        default=1,
        ge=1,
        le=31,
        description=(
            "Day of week (1=Mon … 7=Sun) for weekly; "
            "day of month (1–31) for monthly; ignored for daily"
        ),
    )

    class Config:
        json_schema_extra = {
            "example": {
                "regularity": "weekly",
                "time": "08:00",
                "day_number": 1,
            }
        }


# =============================================================================
# Scouts — request models
# =============================================================================


class CreateScoutRequest(BaseModel):
    """Request to create a new scout."""

    name: str = Field(..., min_length=1, max_length=120, description="Display name for the scout")
    type: ScoutType = Field(default="pulse", description="Scout type: 'web' (Page Scout) or 'pulse' (Smart Scout)")
    schedule: ScheduleConfig

    # Web scout fields
    url: Optional[str] = Field(None, description="URL to monitor (required for web scouts)")

    # Shared optional fields
    criteria: Optional[str] = Field(None, max_length=500, description="Optional criteria to narrow AI analysis")

    # Pulse scout fields
    location: Optional[GeocodedLocation] = Field(None, description="Geo-targeted location (pulse scouts)")
    topic: Optional[str] = Field(None, max_length=200, description="Topic keyword (pulse scouts)")
    source_mode: Literal["reliable", "niche"] = Field(
        default="niche",
        description="Source mode: 'reliable' for established outlets, 'niche' for community/underreported content",
    )
    excluded_domains: Optional[list[str]] = Field(
        None,
        description="Per-scout domain blacklist (pulse scouts)",
    )

    @model_validator(mode="after")
    def validate_scout_type_requirements(self) -> "CreateScoutRequest":
        """Enforce type-specific required fields."""
        if self.type == "web":
            if not (self.url and self.url.strip()):
                raise ValueError("url is required for web scouts")
        elif self.type == "pulse":
            if not self.location and not self.topic:
                raise ValueError("At least one of location or topic is required for pulse scouts")
        return self

    class Config:
        json_schema_extra = {
            "example": {
                "name": "Local news — Vienna",
                "type": "pulse",
                "schedule": {"regularity": "daily", "time": "07:00"},
                "location": {
                    "displayName": "Vienna, Austria",
                    "city": "Vienna",
                    "country": "AT",
                    "locationType": "city",
                },
            }
        }


# =============================================================================
# Scouts — response models
# =============================================================================


class ScoutResponse(BaseModel):
    """Scout summary returned in list and detail responses."""

    name: str = Field(..., description="Scout name (also used as identifier)")
    type: str = Field(..., description="Scout type: 'web' or 'pulse'")
    status: Optional[bool] = Field(None, description="Last run scraper status (True = success)")
    schedule: Optional[ScheduleConfig] = Field(None, description="Schedule configuration")
    location: Optional[GeocodedLocation] = Field(None, description="Geo-targeted location (pulse scouts)")
    topic: Optional[str] = Field(None, description="Topic keyword (pulse scouts)")
    url: Optional[str] = Field(None, description="Monitored URL (web scouts)")
    criteria: Optional[str] = Field(None, description="AI analysis criteria")
    source_mode: Optional[str] = Field(None, description="Source mode (pulse scouts)")
    last_run: Optional[str] = Field(None, description="Formatted timestamp of last run")
    card_summary: Optional[str] = Field(None, description="AI-generated summary from latest run")
    created_at: Optional[str] = Field(None, description="ISO 8601 creation timestamp (UTC)")


class ScoutListResponse(BaseModel):
    """Response listing all scouts for the authenticated user."""

    scouts: list[ScoutResponse]
    count: int


class ScoutRunResponse(BaseModel):
    """Result of a scout run (run-now or historical TIME# record)."""

    scraper_status: bool = Field(..., description="True if the scrape/search completed successfully")
    criteria_status: bool = Field(..., description="True if the AI criteria check passed")
    summary: str = Field(default="", description="AI-generated run summary")
    notification_sent: Optional[bool] = Field(None, description="Whether an email notification was sent")
    change_status: Optional[str] = Field(None, description="Change status for web scouts (changed/unchanged)")


class ScoutDetailResponse(BaseModel):
    """Detailed scout response including recent run history."""

    # Scout metadata (same fields as ScoutResponse)
    name: str
    type: str
    status: Optional[bool] = None
    schedule: Optional[ScheduleConfig] = None
    location: Optional[GeocodedLocation] = None
    topic: Optional[str] = None
    url: Optional[str] = None
    criteria: Optional[str] = None
    source_mode: Optional[str] = None
    last_run: Optional[str] = None
    card_summary: Optional[str] = None
    created_at: Optional[str] = None

    # Extended detail fields
    recent_runs: list[ScoutRunResponse] = Field(
        default_factory=list,
        description="Most recent run results (TIME# records)",
    )
    recent_executions: list[dict] = Field(
        default_factory=list,
        description="Most recent EXEC# summaries",
    )


# =============================================================================
# Information Units
# =============================================================================


class UnitResponse(BaseModel):
    """Single information unit extracted from a scout run."""

    id: str = Field(..., description="Unit ID (unit_id)")
    statement: str = Field(..., description="Concise factual statement (1-2 sentences)")
    type: str = Field(..., description="Unit type: fact, event, or entity_update")
    entities: list[str] = Field(default_factory=list, description="Named entities mentioned")
    source_url: str = Field(..., description="Source article URL")
    source_domain: str = Field(..., description="Source domain")
    source_title: str = Field(..., description="Source article title")
    scout_name: Optional[str] = Field(None, description="Name of the scout that produced this unit")
    topic: Optional[str] = Field(None, description="Topic associated with this unit")
    date: Optional[str] = Field(None, description="Publication date (if known)")
    created_at: str = Field(..., description="ISO 8601 timestamp when the unit was extracted")
    used_in_article: bool = Field(default=False, description="Whether this unit has been used in an export")


class UnitListResponse(BaseModel):
    """Response listing information units."""

    units: list[UnitResponse]
    count: int


class UnitSearchResponse(BaseModel):
    """Response from semantic search over information units."""

    units: list[dict] = Field(..., description="Units with similarity_score field added")
    count: int
    query: str = Field(..., description="The search query that was executed")


# =============================================================================
# Errors
# =============================================================================


class ErrorResponse(BaseModel):
    """Standard error response for v1 API."""

    error: str = Field(..., description="Human-readable error message")
    code: str = Field(..., description="Machine-readable error code (e.g. 'not_found', 'validation_error')")

    class Config:
        json_schema_extra = {
            "example": {
                "error": "Scout not found",
                "code": "not_found",
            }
        }
