"""
Shared Pydantic schemas used by multiple modules.

PURPOSE: Common data models shared across routers and services.
Currently contains AINewsArticle, the canonical article representation
used throughout the search and notification pipeline.

DEPENDS ON: (pydantic only — no app imports)
USED BY: schemas/pulse.py, services/news_utils.py, routers/pulse.py
"""
from typing import Optional

from pydantic import BaseModel, Field


class AINewsArticle(BaseModel):
    """Article returned by AI agent with verification."""
    title: str = Field(..., description="Article title")
    url: str = Field(..., description="Article URL")
    source: str = Field(..., description="News source/domain")
    summary: str = Field("", description="AI-generated summary")
    date: Optional[str] = Field(None, description="Publication date")
    imageUrl: Optional[str] = Field(None, description="Article image URL")
    verified: bool = Field(True, description="Whether content was verified via scrape")
