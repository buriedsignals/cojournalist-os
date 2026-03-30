"""
Tests for POST /social/test endpoint (baseline scan).

Verifies:
- Successful profile scan returns post_ids, preview_posts, and posts_data
- Invalid profile returns valid=False with no baseline data
- Apify failure returns valid=True with empty baseline + warning
- Response schema includes new baseline fields
"""
import pytest
from unittest.mock import AsyncMock, patch

from app.schemas.social import (
    SocialTestRequest,
    SocialTestResponse,
    NormalizedPost,
)


def _make_normalized_posts(count: int = 3) -> list[NormalizedPost]:
    """Create mock NormalizedPost list for testing."""
    posts = []
    for i in range(count):
        posts.append(NormalizedPost(
            id=f"post_{i}",
            url=f"https://www.instagram.com/p/CODE{i}/",
            text=f"Test caption for post {i}" + " extra text" * 10,
            author="testuser",
            timestamp=f"2025-01-0{i + 1}T00:00:00Z",
            image_urls=[f"https://cdn.example.com/img{i}.jpg"],
            platform="instagram",
            engagement={"likes": i * 10, "comments": i},
        ))
    return posts


class TestSocialTestResponseSchema:
    """Verify the updated SocialTestResponse schema has baseline fields."""

    def test_response_with_baseline_data(self):
        resp = SocialTestResponse(
            valid=True,
            profile_url="https://www.instagram.com/testuser/",
            post_ids=["p1", "p2"],
            preview_posts=[{"id": "p1", "text": "Hello", "timestamp": "2025-01-01"}],
            posts_data=[{"post_id": "p1", "caption_truncated": "Hello", "timestamp": "2025-01-01"}],
        )
        assert resp.valid is True
        assert len(resp.post_ids) == 2
        assert len(resp.preview_posts) == 1
        assert len(resp.posts_data) == 1

    def test_response_defaults_empty_lists(self):
        resp = SocialTestResponse(
            valid=True,
            profile_url="https://www.instagram.com/testuser/",
        )
        assert resp.post_ids == []
        assert resp.preview_posts == []
        assert resp.posts_data == []
        assert resp.error is None

    def test_response_with_error_and_empty_baseline(self):
        resp = SocialTestResponse(
            valid=True,
            profile_url="https://www.instagram.com/testuser/",
            error="Profile valid but baseline scan failed: timeout",
            post_ids=[],
            preview_posts=[],
            posts_data=[],
        )
        assert resp.valid is True
        assert resp.error is not None
        assert len(resp.post_ids) == 0


@pytest.mark.asyncio
async def test_test_endpoint_success():
    """Full scan: HEAD ok + Apify returns posts."""
    mock_posts = _make_normalized_posts(3)

    with patch("app.routers.social.validate_profile", new_callable=AsyncMock) as mock_validate, \
         patch("app.routers.social.scrape_profile", new_callable=AsyncMock) as mock_scrape:

        mock_validate.return_value = (True, "https://www.instagram.com/testuser/")
        mock_scrape.return_value = mock_posts

        from app.routers.social import test_social_profile

        request = SocialTestRequest(platform="instagram", handle="testuser")
        # Simulate the dependency injection with a mock user
        result = await test_social_profile(request, user={"user_id": "u1"})

    assert result.valid is True
    assert result.profile_url == "https://www.instagram.com/testuser/"
    assert len(result.post_ids) == 3
    assert result.post_ids == ["post_0", "post_1", "post_2"]
    assert len(result.preview_posts) == 3
    # Preview text is truncated to 120 chars
    assert len(result.preview_posts[0]["text"]) <= 120
    assert len(result.posts_data) == 3
    # posts_data has snapshot format
    assert result.posts_data[0]["post_id"] == "post_0"
    assert "caption_truncated" in result.posts_data[0]
    assert result.error is None


@pytest.mark.asyncio
async def test_test_endpoint_invalid_profile():
    """HEAD check fails: profile doesn't exist."""
    with patch("app.routers.social.validate_profile", new_callable=AsyncMock) as mock_validate:
        mock_validate.return_value = (False, "https://www.instagram.com/noexist/")

        from app.routers.social import test_social_profile

        request = SocialTestRequest(platform="instagram", handle="noexist")
        result = await test_social_profile(request, user={"user_id": "u1"})

    assert result.valid is False
    assert result.error == "Profile not found or inaccessible"
    assert result.post_ids == []
    assert result.preview_posts == []
    assert result.posts_data == []


@pytest.mark.asyncio
async def test_test_endpoint_apify_failure():
    """HEAD ok but Apify scrape fails: return valid=True with warning."""
    with patch("app.routers.social.validate_profile", new_callable=AsyncMock) as mock_validate, \
         patch("app.routers.social.scrape_profile", new_callable=AsyncMock) as mock_scrape:

        mock_validate.return_value = (True, "https://www.instagram.com/testuser/")
        mock_scrape.side_effect = Exception("Apify timeout after 120s")

        from app.routers.social import test_social_profile

        request = SocialTestRequest(platform="instagram", handle="testuser")
        result = await test_social_profile(request, user={"user_id": "u1"})

    assert result.valid is True
    assert "baseline scan failed" in result.error
    assert result.post_ids == []
    assert result.preview_posts == []
    assert result.posts_data == []


@pytest.mark.asyncio
async def test_test_endpoint_empty_scrape():
    """HEAD ok, Apify returns empty list (new/private account)."""
    with patch("app.routers.social.validate_profile", new_callable=AsyncMock) as mock_validate, \
         patch("app.routers.social.scrape_profile", new_callable=AsyncMock) as mock_scrape:

        mock_validate.return_value = (True, "https://www.instagram.com/newuser/")
        mock_scrape.return_value = []

        from app.routers.social import test_social_profile

        request = SocialTestRequest(platform="instagram", handle="newuser")
        result = await test_social_profile(request, user={"user_id": "u1"})

    assert result.valid is True
    assert result.error is None
    assert result.post_ids == []
    assert result.preview_posts == []
    assert result.posts_data == []


@pytest.mark.asyncio
async def test_test_endpoint_truncates_preview():
    """Preview text is truncated to 120 chars, snapshot to 200 chars."""
    long_text = "A" * 300
    mock_posts = [NormalizedPost(
        id="long1",
        url="https://www.instagram.com/p/LONG/",
        text=long_text,
        author="verbose",
        timestamp="2025-01-01T00:00:00Z",
        image_urls=["https://cdn.example.com/img.jpg"],
        platform="instagram",
    )]

    with patch("app.routers.social.validate_profile", new_callable=AsyncMock) as mock_validate, \
         patch("app.routers.social.scrape_profile", new_callable=AsyncMock) as mock_scrape:

        mock_validate.return_value = (True, "https://www.instagram.com/verbose/")
        mock_scrape.return_value = mock_posts

        from app.routers.social import test_social_profile

        request = SocialTestRequest(platform="instagram", handle="verbose")
        result = await test_social_profile(request, user={"user_id": "u1"})

    assert len(result.preview_posts[0]["text"]) == 120
    assert len(result.posts_data[0]["caption_truncated"]) == 200


@pytest.mark.asyncio
async def test_test_endpoint_scrape_called_with_max_20():
    """Verify scrape_profile is called with max_items=20 (matches execute)."""
    with patch("app.routers.social.validate_profile", new_callable=AsyncMock) as mock_validate, \
         patch("app.routers.social.scrape_profile", new_callable=AsyncMock) as mock_scrape:

        mock_validate.return_value = (True, "https://x.com/testuser")
        mock_scrape.return_value = []

        from app.routers.social import test_social_profile

        request = SocialTestRequest(platform="x", handle="testuser")
        await test_social_profile(request, user={"user_id": "u1"})

    mock_scrape.assert_called_once_with(
        platform="x",
        handle="testuser",
        max_items=20,
    )
