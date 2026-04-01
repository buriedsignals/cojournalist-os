"""
Feedback router — submit feedback issues to Linear.

PURPOSE: POST /feedback creates a Linear issue tagged with the coJournalist
label plus a type label (bug, feature, improvement). Requires user auth.

DEPENDS ON: dependencies (get_current_user), config (get_settings), httpx
USED BY: main.py (router mount), frontend FeedbackModal
"""
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
import httpx
from app.dependencies import get_current_user
from app.config import get_settings

router = APIRouter()

# Linear workspace constants — IDs are stable, no need for env vars
_LINEAR_TEAM_ID = "c80ef17d-cce9-4f37-9e1d-1b2e5ca62c1f"
_LABEL_COJOURNALIST = "874d33fd-8db2-49eb-88b0-e13077e65359"
_LABEL_BUG = "8ddfb490-603b-440e-931a-7054d8025dfc"
_LABEL_FEATURE = "752a7939-908d-4e6f-bba3-09514e6ab32e"
_LABEL_IMPROVEMENT = "aff4a346-532c-4874-8cf4-3992fa57c795"

_TYPE_LABEL_MAP = {
    "bug": _LABEL_BUG,
    "feature": _LABEL_FEATURE,
    "other": _LABEL_IMPROVEMENT,
}


class FeedbackRequest(BaseModel):
    title: str
    type: Literal["bug", "feature", "other"]
    description: str = ""
    device: str = ""
    browser: str = ""
    screenshot_base64: str = ""
    screenshot_filename: str = ""
    screenshot_content_type: str = "image/png"


class FeedbackResponse(BaseModel):
    url: str


async def _upload_screenshot(api_key: str, base64_data: str, filename: str, content_type: str) -> str | None:
    """Upload a screenshot to Linear and return the asset URL, or None on failure."""
    import base64 as _b64
    try:
        image_bytes = _b64.b64decode(base64_data)
        mutation = """
        mutation FileUpload($contentType: String!, $filename: String!, $size: Int!) {
          fileUpload(contentType: $contentType, filename: $filename, size: $size) {
            uploadFile {
              uploadUrl
              assetUrl
              headers { key value }
            }
          }
        }
        """
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                "https://api.linear.app/graphql",
                headers={"Authorization": api_key, "Content-Type": "application/json"},
                json={"query": mutation, "variables": {
                    "contentType": content_type,
                    "filename": filename,
                    "size": len(image_bytes),
                }},
                timeout=10.0,
            )
            resp.raise_for_status()
            data = resp.json()
            upload_file = data["data"]["fileUpload"]["uploadFile"]
            upload_headers = {h["key"]: h["value"] for h in upload_file["headers"]}
            upload_headers["Content-Type"] = content_type
            await client.put(upload_file["uploadUrl"], content=image_bytes, headers=upload_headers, timeout=30.0)
            return upload_file["assetUrl"]
    except Exception:
        return None


@router.post("/feedback", response_model=FeedbackResponse)
async def submit_feedback(
    request: FeedbackRequest,
    current_user=Depends(get_current_user)
):
    settings = get_settings()

    type_label_id = _TYPE_LABEL_MAP[request.type]

    parts = []
    if request.description:
        parts.append(request.description)

    # Bug metadata
    if request.type == "bug":
        meta = []
        if request.device:
            meta.append(f"**Device:** {request.device}")
        if request.browser:
            meta.append(f"**Browser:** {request.browser}")
        if meta:
            parts.append("\n".join(meta))

    # Screenshot
    if request.screenshot_base64 and request.screenshot_filename:
        asset_url = await _upload_screenshot(
            settings.linear_api_key,
            request.screenshot_base64,
            request.screenshot_filename,
            request.screenshot_content_type,
        )
        if asset_url:
            parts.append(f"![Screenshot]({asset_url})")

    # Attribution
    parts.append(f"---\n*Submitted by: {current_user.get('email', current_user.get('user_id', 'unknown'))} via coJournalist*")

    description = "\n\n".join(parts)

    mutation = """
    mutation IssueCreate($input: IssueCreateInput!) {
      issueCreate(input: $input) {
        success
        issue { id identifier url title }
      }
    }
    """
    variables = {
        "input": {
            "teamId": _LINEAR_TEAM_ID,
            "title": request.title,
            "description": description,
            "labelIds": [_LABEL_COJOURNALIST, type_label_id],
        }
    }

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                "https://api.linear.app/graphql",
                headers={
                    "Authorization": settings.linear_api_key,
                    "Content-Type": "application/json",
                },
                json={"query": mutation, "variables": variables},
                timeout=10.0,
            )
            resp.raise_for_status()
            data = resp.json()
            issue = data["data"]["issueCreate"]["issue"]
            return FeedbackResponse(url=issue["url"])
    except Exception:
        raise HTTPException(status_code=502, detail="Failed to submit feedback")
