"""
Pydantic schemas for scout execution endpoints.

PURPOSE: Shared data models used across multiple routers and services:
GeocodedLocation (geocoded place data from MapTiler), Coordinates,
SupportedLanguage (12-language enum for email localization), and
LocationType.

DEPENDS ON: (pydantic only — no app imports)
USED BY: schemas/pulse.py, models/responses.py, services/scout_service.py,
    services/atomic_unit_service.py, services/feed_search_service.py,
    routers/scouts.py, routers/units.py
"""
from typing import Optional, Literal
from pydantic import BaseModel

# Supported language codes for email localization
SupportedLanguage = Literal["en", "no", "de", "fr", "es", "it", "pt", "nl", "sv", "da", "fi", "pl"]


class Coordinates(BaseModel):
    """Nested coordinates structure - matches frontend format."""
    lat: float
    lon: float


LocationType = Literal["city", "state", "country"]


class GeocodedLocation(BaseModel):
    """Location data from geocoding - matches frontend format."""
    displayName: str
    city: Optional[str] = None
    state: Optional[str] = None
    country: str  # 2-letter ISO code (e.g., "NO", "CH")
    locationType: Optional[LocationType] = None
    maptilerId: Optional[str] = None
    coordinates: Optional[Coordinates] = None


