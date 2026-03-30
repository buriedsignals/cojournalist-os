"""Supabase implementation of AuthPort.

Uses Supabase JWT validation for user authentication. Gets email from
auth.users via supabase-py admin API. Service key verification uses
HMAC comparison identical to the AWS adapter.

DEPENDS ON: config (supabase_jwt_secret, supabase_url, supabase_service_key,
            internal_service_key), ports.auth (AuthPort)
USED BY: dependencies/providers.py (DI wiring)
"""
from __future__ import annotations

import hmac
import logging
from typing import Optional

import jwt as pyjwt
from fastapi import HTTPException, Request, status
from supabase import AsyncClient, acreate_client

from app.config import get_settings
from app.ports.auth import AuthPort

logger = logging.getLogger(__name__)


class SupabaseAuth(AuthPort):
    """Supabase JWT-based authentication."""

    def __init__(self, user_storage=None):
        settings = get_settings()
        self.jwt_secret = settings.supabase_jwt_secret
        self.internal_service_key = settings.internal_service_key
        self.user_storage = user_storage
        self._supabase_url = settings.supabase_url
        self._supabase_service_key = settings.supabase_service_key
        self._supabase_client: AsyncClient | None = None

    async def get_current_user(self, request: Request) -> dict:
        """Validate Supabase JWT from Authorization header and return user data.

        The frontend sends the Supabase access token as a Bearer token.
        We decode it using the Supabase JWT secret and look up the user
        in user_preferences.

        Returns:
            User dict with user_id, timezone, preferences, etc.

        Raises:
            HTTPException 401: If token is missing, invalid, or user not found.
        """
        auth_header = request.headers.get("Authorization", "")
        token = auth_header.replace("Bearer ", "") if auth_header.startswith("Bearer ") else ""

        if not token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Missing authorization token",
            )

        try:
            payload = pyjwt.decode(
                token,
                self.jwt_secret,
                algorithms=["HS256"],
                options={"verify_aud": False},
            )
        except pyjwt.ExpiredSignatureError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token has expired",
            )
        except pyjwt.InvalidTokenError as e:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Invalid token: {e}",
            )

        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token: missing sub claim",
            )

        user = await self.user_storage.get_user(user_id)
        if not user:
            # First-time user -- create preferences record
            user = await self.user_storage.create_or_update_user(user_id, {})

        user["user_id"] = user_id
        return user

    async def get_user_email(self, user_id: str) -> Optional[str]:
        """Get user email from Supabase auth.users via async admin API.

        Uses the async Supabase client (acreate_client) to avoid blocking
        the event loop. The client is lazily initialized on first call.
        """
        try:
            if self._supabase_client is None:
                self._supabase_client = await acreate_client(
                    self._supabase_url,
                    self._supabase_service_key,
                )
            result = await self._supabase_client.auth.admin.get_user_by_id(user_id)
            return result.user.email
        except Exception as e:
            logger.error(f"Failed to fetch email from Supabase for {user_id}: {e}")
            return None

    async def verify_service_key(self, key: str) -> bool:
        """Verify internal service key using constant-time comparison."""
        if not self.internal_service_key or not key:
            return False
        return hmac.compare_digest(key, self.internal_service_key)
