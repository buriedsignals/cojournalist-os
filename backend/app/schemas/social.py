"""
Pydantic schemas for social media scout endpoints.
"""
from typing import Optional, List
from pydantic import BaseModel, Field, field_validator

from app.models.modes import SocialPlatform, SocialMonitorMode


class SocialTestRequest(BaseModel):
    platform: SocialPlatform
    handle: str

    @field_validator("handle")
    @classmethod
    def clean_handle(cls, v: str) -> str:
        return v.lstrip("@").strip()


class SocialTestResponse(BaseModel):
    valid: bool
    profile_url: str
    error: Optional[str] = None
    post_ids: List[str] = []  # baseline post IDs for snapshot
    preview_posts: List[dict] = []  # preview for the user (truncated)
    posts_data: List[dict] = []  # full snapshot data to store at schedule time


class SocialExecuteRequest(BaseModel):
    userId: str
    scraperName: str
    platform: SocialPlatform
    profile_handle: str
    monitor_mode: SocialMonitorMode
    track_removals: bool = False
    criteria: Optional[str] = None
    topic: Optional[str] = Field(None, max_length=200)
    preferred_language: str = "en"
    skip_credit_charge: bool = False


class NormalizedPost(BaseModel):
    id: str
    url: str
    text: str
    author: str
    timestamp: str
    image_urls: List[str] = []
    video_url: Optional[str] = None
    platform: SocialPlatform
    engagement: dict = {}


class PostSnapshot(BaseModel):
    post_id: str
    caption_truncated: str
    image_url: Optional[str] = None
    timestamp: str
