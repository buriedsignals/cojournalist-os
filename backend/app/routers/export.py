"""
Export Router — API endpoints for feed export features.

PURPOSE: Generate article drafts from selected atomic units (POST /export/generate),
auto-select best units for a topic (POST /export/auto-select), and push
drafts to external CMS via API (POST /export/cms). Each export costs 1 credit.

DEPENDS ON: dependencies (session cookie auth, credit decrement),
    utils/credits (credit validation)
USED BY: frontend (export panel), main.py (router mount)
"""

import asyncio
import ipaddress
import logging
from datetime import datetime, timezone
from urllib.parse import urlparse

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from slowapi import Limiter
from slowapi.util import get_remote_address
from typing import List, Literal, Optional

from ..dependencies import get_current_user, decrement_credit, validate_credits
from ..services.export_generator import ExportGeneratorService
from ..services.user_service import UserService
from ..utils.pricing import CREDIT_COSTS

logger = logging.getLogger(__name__)

# Rate limiter for expensive AI operations
limiter = Limiter(key_func=get_remote_address)

router = APIRouter(prefix="/export", tags=["export"])

# Initialize service
generator = ExportGeneratorService()


class UnitInput(BaseModel):
    """Input unit for export generation."""
    statement: str = Field(..., max_length=1000)
    source_title: str = Field(..., max_length=500)
    source_url: str = Field(..., max_length=2000)
    unit_type: Optional[Literal["fact", "event", "entity_update"]] = "fact"
    entities: Optional[List[str]] = Field(default=[], max_items=20)
    source_domain: Optional[str] = Field(default=None, max_length=200)
    topic: Optional[str] = Field(default=None, max_length=200)


class GenerateExportRequest(BaseModel):
    """Request to generate an export."""
    units: List[UnitInput]
    location_name: str
    language: Optional[str] = None
    custom_system_prompt: Optional[str] = Field(None, max_length=3000)


class SourceOutput(BaseModel):
    """Source reference in output."""
    title: str
    url: str


class SectionOutput(BaseModel):
    """A section of the article draft."""
    heading: str
    content: str


class GenerateExportResponse(BaseModel):
    """Response with generated export."""
    title: str
    headline: str
    sections: List[SectionOutput]
    gaps: List[str]
    bullet_points: List[str]
    sources: List[SourceOutput]


@router.post("/generate", response_model=GenerateExportResponse)
@limiter.limit("10/minute")
async def generate_export(
    request: Request,
    body: GenerateExportRequest,
    user: dict = Depends(get_current_user)
):
    """
    Generate an export from selected information units.

    Uses AI to synthesize the provided units into a structured export
    with title, headline, and bullet points citing sources.
    """
    if not body.units:
        raise HTTPException(status_code=400, detail="No units provided")

    if len(body.units) > 20:
        raise HTTPException(status_code=400, detail="Maximum 20 units allowed")

    # Validate credits before generation
    user_id = user.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="User ID not found")
    org_id = user.get("org_id")
    await validate_credits(user_id, CREDIT_COSTS["feed_export"], org_id=org_id)

    logger.info(f"[ExportRouter] Generating draft from {len(body.units)} units")

    try:
        # Convert to dict format for service
        units_data = [
            {
                "statement": u.statement,
                "source_title": u.source_title,
                "source_url": u.source_url,
                "unit_type": u.unit_type or "fact",
                "entities": u.entities or [],
                "source_domain": u.source_domain,
                "topic": u.topic
            }
            for u in body.units
        ]

        # Use explicit language if provided, fallback to user preference
        language = body.language or user.get("preferred_language", "en")

        result = await generator.generate_export(
            units=units_data,
            location_name=body.location_name,
            language=language,
            custom_system_prompt=body.custom_system_prompt
        )

        # Deduct credit after successful generation
        await decrement_credit(user_id, org_id=org_id)

        return GenerateExportResponse(
            title=result["title"],
            headline=result["headline"],
            sections=[
                SectionOutput(heading=s.get("heading", ""), content=s.get("content", ""))
                for s in result.get("sections", [])
            ],
            gaps=result.get("gaps", []),
            bullet_points=result["bullet_points"],
            sources=[
                SourceOutput(title=s["title"], url=s["url"])
                for s in result["sources"]
            ]
        )

    except Exception as e:
        logger.error(f"[ExportRouter] Draft generation failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to generate export: {str(e)}")


# ==================== AI Auto-Select ====================

class AutoSelectUnitInput(BaseModel):
    """Unit data for auto-selection scoring."""
    unit_id: str
    statement: str = Field(..., max_length=1000)
    entities: List[str] = Field(default=[])
    source_title: str = Field(..., max_length=500)
    created_at: str  # ISO timestamp
    date: Optional[str] = None  # Event date (YYYY-MM-DD) from LLM extraction
    unit_type: Optional[str] = "fact"
    scout_type: Optional[str] = None


class AutoSelectRequest(BaseModel):
    """Request to auto-select relevant units."""
    units: List[AutoSelectUnitInput] = Field(..., min_length=1, max_length=100)
    prompt: str = Field(..., max_length=2000)
    location: Optional[str] = Field(default=None, max_length=500)
    topic: Optional[str] = Field(default=None, max_length=200)


class AutoSelectResponse(BaseModel):
    """Response with AI-selected unit IDs."""
    selected_unit_ids: List[str]
    selection_summary: str


@router.post("/auto-select", response_model=AutoSelectResponse)
@limiter.limit("10/minute")
async def auto_select_units(
    request: Request,
    body: AutoSelectRequest,
    user: dict = Depends(get_current_user)
):
    """
    AI-powered selection of relevant information units.
    """
    user_id = user.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="User ID not found")
    org_id = user.get("org_id")

    await validate_credits(user_id, CREDIT_COSTS["feed_export"], org_id=org_id)

    logger.info(f"[ExportRouter] Auto-selecting from {len(body.units)} units, prompt: {body.prompt[:50]}")

    try:
        result = await generator.auto_select_units(
            units=[u.dict() for u in body.units],
            prompt=body.prompt,
            location=body.location,
            topic=body.topic,
        )

        await decrement_credit(user_id, org_id=org_id)

        return AutoSelectResponse(
            selected_unit_ids=result["selected_unit_ids"],
            selection_summary=result["selection_summary"],
        )

    except Exception as e:
        logger.error(f"[ExportRouter] Auto-select failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Auto-selection failed: {str(e)}")


# ==================== CMS Export ====================

class ExportUnitInput(BaseModel):
    """Minimal unit data for CMS export."""
    statement: str
    source_title: str
    source_url: str


class DraftInput(BaseModel):
    """Draft structure for CMS export."""
    title: str
    headline: str
    sections: List[SectionOutput] = []
    gaps: List[str] = []
    bullet_points: List[str] = []
    sources: List[SourceOutput] = []


class ExportToCmsRequest(BaseModel):
    """Request to export draft to user's CMS."""
    draft: DraftInput
    units: List[ExportUnitInput] = []


def _validate_cms_url(url: str) -> None:
    """Validate CMS URL for SSRF protection."""
    parsed = urlparse(url)
    if parsed.scheme != "https":
        raise HTTPException(status_code=400, detail="CMS API URL must use HTTPS")
    hostname = parsed.netloc.lower()
    if not hostname:
        raise HTTPException(status_code=400, detail="Invalid CMS URL")
    host = hostname.split(":")[0] if ":" in hostname else hostname
    try:
        ip = ipaddress.ip_address(host)
        if ip.is_private or ip.is_loopback or ip.is_reserved or ip.is_link_local:
            raise HTTPException(status_code=400, detail="CMS API URL cannot target private/internal addresses")
    except ValueError:
        pass  # hostname is not an IP — fine


@router.post("/to-cms")
@limiter.limit("10/minute")
async def export_to_cms(
    request: Request,
    body: ExportToCmsRequest,
    user: dict = Depends(get_current_user),
):
    """Proxy export to user's configured CMS API endpoint."""
    user_id = user.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="User ID not found")

    # Fetch CMS config from DynamoDB
    try:
        us = UserService()
        cms_config = await us.get_cms_config(user_id)
    except Exception as exc:
        logger.error(f"[ExportRouter] Failed to fetch user config for {user_id}: {exc}")
        raise HTTPException(status_code=500, detail="Failed to fetch user configuration")

    cms_url = cms_config.get("cms_api_url")
    cms_token = cms_config.get("cms_api_token")

    if not cms_url:
        raise HTTPException(status_code=400, detail="No CMS API endpoint configured")

    # Validate URL for SSRF protection
    _validate_cms_url(cms_url)

    # Build payload
    export_payload = {
        "draft": body.draft.dict(),
        "units": [u.dict() for u in body.units],
        "exported_at": datetime.now(timezone.utc).isoformat(),
    }

    # POST to CMS
    headers = {"Content-Type": "application/json"}
    if cms_token:
        headers["Authorization"] = f"Bearer {cms_token}"

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(cms_url, json=export_payload, headers=headers)
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="CMS endpoint timed out")
    except httpx.RequestError as exc:
        logger.error(f"[ExportRouter] CMS request failed: {exc}")
        raise HTTPException(status_code=502, detail="Failed to connect to CMS endpoint")

    if response.status_code >= 400:
        logger.warning(f"[ExportRouter] CMS returned {response.status_code} for user {user_id}")
        raise HTTPException(status_code=502, detail=f"CMS returned {response.status_code}")

    logger.info(f"[ExportRouter] Successfully exported to CMS for user {user_id}")
    return {"success": True}
