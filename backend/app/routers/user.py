"""
User router for user-specific settings and preferences.

PURPOSE: GET/PUT /user/preferences for language, timezone, excluded domains,
and CMS configuration. Stores preferences in DynamoDB via UserService.

DEPENDS ON: dependencies (session auth), services/user_service (DynamoDB),
    models/responses (UserPreferencesResponse)
USED BY: frontend (settings panel), main.py (router mount)
"""
import asyncio
import ipaddress
import logging
from fastapi import APIRouter, Depends, HTTPException, status
from typing import Optional, List
from urllib.parse import urlparse
from pydantic import BaseModel, Field, field_validator
from app.dependencies import get_current_user
from app.models.responses import UserPreferencesResponse
from app.services.user_service import UserService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/user", tags=["user"])

_user_service: Optional[UserService] = None


def _get_user_service() -> UserService:
    global _user_service
    if _user_service is None:
        _user_service = UserService()
    return _user_service


class UpdatePreferencesRequest(BaseModel):
    """Request to update user preferences (language, timezone, excluded domains, CMS config)."""
    preferred_language: Optional[str] = Field(None, min_length=2, max_length=5, description="ISO 639-1 language code")
    timezone: Optional[str] = Field(None, description="IANA timezone identifier")
    excluded_domains: Optional[List[str]] = Field(None, description="Domains to exclude from Pulse results (max 50)")
    cms_api_url: Optional[str] = Field(None, max_length=2000, description="CMS API endpoint URL")
    cms_api_token: Optional[str] = Field(None, max_length=500, description="Bearer token for CMS API")

    @field_validator('cms_api_url')
    @classmethod
    def validate_cms_url(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        v = v.strip()
        if not v:
            return ""  # Empty string clears the URL
        parsed = urlparse(v)
        if parsed.scheme != "https":
            raise ValueError("CMS API URL must use HTTPS")
        hostname = parsed.netloc.lower()
        if not hostname:
            raise ValueError("Invalid URL - no hostname found")
        # Block private/internal IPs
        host = hostname.split(":")[0] if ":" in hostname else hostname
        try:
            ip = ipaddress.ip_address(host)
            if ip.is_private or ip.is_loopback or ip.is_reserved or ip.is_link_local:
                raise ValueError("CMS API URL cannot target private/internal addresses")
        except ValueError as ip_err:
            if "private" in str(ip_err) or "cannot target" in str(ip_err):
                raise
            # hostname is not an IP address — fine
        return v

    @field_validator('excluded_domains')
    @classmethod
    def clean_excluded_domains(cls, v: Optional[List[str]]) -> Optional[List[str]]:
        if v is None:
            return None
        cleaned = []
        for domain in v:
            # Strip protocols, www., trailing slashes, lowercase
            d = domain.strip().lower()
            if "://" in d:
                d = urlparse(d).netloc or d.split("://", 1)[1]
            d = d.replace("www.", "").rstrip("/")
            if d and d not in cleaned:
                cleaned.append(d)
        return cleaned[:50]  # Cap at 50


@router.get("/preferences", response_model=UserPreferencesResponse)
async def get_user_preferences(
    user: dict = Depends(get_current_user)
):
    """
    Get user's preferences from DynamoDB.
    """
    user_id = user.get("user_id")

    # Fetch fresh from DynamoDB to get cms_api_url and has_cms_token
    # (get_current_user doesn't include CMS fields)
    user_service = _get_user_service()
    try:
        db_user = await user_service.get_user(user_id)
    except Exception as exc:
        logger.warning(f"Failed to fetch user profile for preferences: {exc}")
        db_user = None

    cms_api_url = db_user.get("cms_api_url") if db_user else None
    has_cms_token = db_user.get("has_cms_token", False) if db_user else False

    return {
        "preferred_language": user.get("preferred_language", "en"),
        "timezone": user.get("timezone"),
        "excluded_domains": user.get("excluded_domains", []),
        "cms_api_url": cms_api_url,
        "has_cms_token": has_cms_token,
    }


@router.put("/preferences")
async def update_user_preferences(
    payload: UpdatePreferencesRequest,
    user: dict = Depends(get_current_user)
):
    """
    Update user's preferred language, timezone, excluded domains, and/or CMS config in DynamoDB.
    """
    user_id = user.get("user_id")

    has_any_field = (
        payload.preferred_language
        or payload.timezone
        or payload.excluded_domains is not None
        or payload.cms_api_url is not None
        or payload.cms_api_token is not None
    )
    if not has_any_field:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one preference field must be provided"
        )

    # Validate timezone if provided
    if payload.timezone:
        from zoneinfo import ZoneInfo
        try:
            ZoneInfo(payload.timezone)
        except (KeyError, Exception):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid timezone identifier: {payload.timezone}"
            )

    try:
        # Build kwargs for UserService.update_preferences
        update_kwargs = {}

        if payload.preferred_language:
            update_kwargs["preferred_language"] = payload.preferred_language
        if payload.timezone:
            update_kwargs["timezone"] = payload.timezone
        if payload.excluded_domains is not None:
            update_kwargs["excluded_domains"] = payload.excluded_domains
        if payload.cms_api_url is not None:
            update_kwargs["cms_api_url"] = payload.cms_api_url if payload.cms_api_url else None
        if payload.cms_api_token is not None:
            # Empty string clears the token
            update_kwargs["cms_api_token"] = payload.cms_api_token if payload.cms_api_token else None

        if update_kwargs:
            user_service = _get_user_service()
            await user_service.update_preferences(user_id, **update_kwargs)

        logger.info(f"Updated preferences for user {user_id}: fields={list(update_kwargs.keys())}")

        # Return the updated fields (exclude cms_api_token from response)
        response_fields = {k: v for k, v in update_kwargs.items() if k != "cms_api_token"}
        return {
            "success": True,
            **response_fields,
        }
    except Exception as exc:
        logger.error(f"Failed to update preferences for {user_id}: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update preferences"
        )
