"""Civic Scout request/response schemas."""
from pydantic import BaseModel, Field, field_validator
from typing import Optional


class CivicDiscoverRequest(BaseModel):
    root_domain: str = Field(..., min_length=1)

    @field_validator("root_domain")
    @classmethod
    def strip_protocol(cls, v: str) -> str:
        v = v.strip()
        for prefix in ("https://", "http://", "www."):
            if v.startswith(prefix):
                v = v[len(prefix):]
        v = v.rstrip("/")
        if not v:
            raise ValueError("root_domain must not be empty after stripping protocol/whitespace")
        return v


class CandidateUrl(BaseModel):
    url: str
    description: str
    confidence: float = Field(ge=0.0, le=1.0)


class CivicDiscoverResponse(BaseModel):
    candidates: list[CandidateUrl]


class CivicExecuteRequest(BaseModel):
    user_id: str
    scraper_name: str
    tracked_urls: list[str]
    criteria: Optional[str] = None
    language: str = "en"


class CivicExecuteResult(BaseModel):
    status: str
    summary: str
    promises_found: int
    new_pdf_urls: list[str]  # Legacy name; holds both PDF and HTML document URLs
    is_duplicate: bool
    promises: list["Promise"] = []


class Promise(BaseModel):
    promise_text: str
    context: str
    source_url: str
    source_date: str
    due_date: Optional[str] = None
    date_confidence: str
    criteria_match: bool


class CivicTestRequest(BaseModel):
    tracked_urls: list[str] = Field(..., min_length=1)
    criteria: Optional[str] = None


class CivicTestResponse(BaseModel):
    valid: bool
    documents_found: int
    sample_promises: list[Promise]
    error: Optional[str] = None
