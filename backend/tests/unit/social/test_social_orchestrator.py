"""
Tests for social_orchestrator normalization, diffing, URL building, and criteria matching.

Verifies:
- Instagram post normalization (nested image URLs, engagement, shortCode)
- X post normalization (author dict handling, text fallback)
- New post identification against previous IDs
- Removed post identification against current IDs
- Profile URL construction for each platform
- Criteria matching via embedding similarity
"""
import pytest
from unittest.mock import patch
from app.schemas.social import NormalizedPost, PostSnapshot
from app.services.social_orchestrator import (
    normalize_instagram_posts,
    normalize_x_posts,
    normalize_facebook_posts,
    identify_new_posts,
    identify_removed_posts,
    build_profile_url,
)


# ---------------------------------------------------------------------------
# Instagram normalization
# ---------------------------------------------------------------------------


class TestNormalizeInstagramPosts:
    def test_basic_post(self):
        """Test with culc72xb7MP3EbaeX (apidojo/instagram-scraper) output format."""
        raw = [
            {
                "id": "123",
                "code": "ABC",
                "caption": "Hello world",
                "owner": {"username": "testuser"},
                "createdAt": "2025-01-01T00:00:00Z",
                "image": {"url": "https://cdn.example.com/img.jpg"},
                "likeCount": 42,
                "commentCount": 5,
            }
        ]
        posts = normalize_instagram_posts(raw)
        assert len(posts) == 1
        p = posts[0]
        assert p.id == "123"
        assert p.url == "https://www.instagram.com/p/ABC/"
        assert p.text == "Hello world"
        assert p.author == "testuser"
        assert p.image_urls == ["https://cdn.example.com/img.jpg"]
        assert p.platform == "instagram"
        assert p.engagement["likes"] == 42
        assert p.engagement["comments"] == 5

    def test_no_image(self):
        """Post without image object gets empty image_urls."""
        raw = [
            {
                "id": "456",
                "code": "DEF",
                "caption": "Text only",
                "owner": {"username": "user2"},
                "createdAt": "2025-01-02T00:00:00Z",
            }
        ]
        posts = normalize_instagram_posts(raw)
        assert posts[0].image_urls == []

    def test_video_post(self):
        """Video posts have isVideo=True and nested video.url."""
        raw = [
            {
                "id": "vid1",
                "code": "VID",
                "caption": "Video post",
                "owner": {"username": "videouser"},
                "createdAt": "2025-01-04T00:00:00Z",
                "isVideo": True,
                "video": {"url": "https://cdn.example.com/video.mp4"},
                "image": {"url": "https://cdn.example.com/thumb.jpg"},
            }
        ]
        posts = normalize_instagram_posts(raw)
        assert posts[0].video_url == "https://cdn.example.com/video.mp4"
        assert posts[0].image_urls == ["https://cdn.example.com/thumb.jpg"]

    def test_non_video_no_video_url(self):
        """Non-video posts should not have video_url even if video key exists."""
        raw = [
            {
                "id": "nv1",
                "code": "NV",
                "caption": "Photo",
                "owner": {"username": "u"},
                "createdAt": "",
                "isVideo": False,
                "video": {"url": "https://cdn.example.com/shouldnt.mp4"},
            }
        ]
        posts = normalize_instagram_posts(raw)
        assert posts[0].video_url is None

    def test_skips_items_without_id(self):
        raw = [
            {"caption": "No ID", "owner": {"username": "u"}},
            {"id": "ok1", "code": "OK", "owner": {"username": "u"}, "createdAt": ""},
        ]
        posts = normalize_instagram_posts(raw)
        assert len(posts) == 1
        assert posts[0].id == "ok1"

    def test_empty_input(self):
        assert normalize_instagram_posts([]) == []

    def test_none_caption(self):
        """Caption can be None for image-only posts."""
        raw = [
            {
                "id": "nc1",
                "code": "NC",
                "caption": None,
                "owner": {"username": "u"},
                "createdAt": "",
            }
        ]
        posts = normalize_instagram_posts(raw)
        assert posts[0].text == ""

    def test_fallback_to_code_as_id(self):
        """When id is missing, code is used as post ID."""
        raw = [
            {
                "code": "ONLY_CODE",
                "caption": "No id field",
                "owner": {"username": "u"},
                "createdAt": "",
            }
        ]
        posts = normalize_instagram_posts(raw)
        assert len(posts) == 1
        assert posts[0].id == "ONLY_CODE"
        assert posts[0].url == "https://www.instagram.com/p/ONLY_CODE/"


# ---------------------------------------------------------------------------
# X normalization
# ---------------------------------------------------------------------------


class TestNormalizeXPosts:
    def test_basic_tweet(self):
        """Test with 61RPP7dywgiy0JPD0 actor output format."""
        raw = [
            {
                "id": "t1",
                "text": "Tweet content",
                "author": {"username": "tweetuser"},
                "created_at": "Mon Jan 01 00:00:00 +0000 2025",
                "favorite_count": 10,
                "retweet_count": 3,
                "reply_count": 1,
            }
        ]
        posts = normalize_x_posts(raw)
        assert len(posts) == 1
        p = posts[0]
        assert p.id == "t1"
        assert p.text == "Tweet content"
        assert p.author == "tweetuser"
        assert p.platform == "x"
        assert p.image_urls == []
        assert p.engagement["likes"] == 10
        assert p.engagement["retweets"] == 3

    def test_url_construction(self):
        raw = [
            {
                "id": "t2",
                "text": "Short",
                "author": {"username": "bob"},
                "created_at": "",
            }
        ]
        posts = normalize_x_posts(raw)
        assert posts[0].url == "https://x.com/bob/status/t2"

    def test_explicit_url(self):
        raw = [
            {
                "id": "t3",
                "text": "Has URL",
                "url": "https://x.com/custom/status/t3",
                "author": {"username": "custom"},
                "created_at": "",
            }
        ]
        posts = normalize_x_posts(raw)
        assert posts[0].url == "https://x.com/custom/status/t3"

    def test_author_string_fallback(self):
        raw = [
            {
                "id": "t4",
                "text": "Str author",
                "author": "plain_string",
                "created_at": "",
            }
        ]
        posts = normalize_x_posts(raw)
        assert posts[0].author == "plain_string"

    def test_skips_items_without_id(self):
        raw = [{"text": "No ID"}]
        posts = normalize_x_posts(raw)
        assert len(posts) == 0

    def test_empty_input(self):
        assert normalize_x_posts([]) == []

    def test_media_extraction(self):
        """Media URLs extracted from extendedEntities.media."""
        raw = [
            {
                "id": "t5",
                "text": "Photo tweet",
                "author": {"username": "photouser"},
                "created_at": "",
                "extendedEntities": {
                    "media": [
                        {"media_url_https": "https://pbs.twimg.com/media/img1.jpg"},
                        {"media_url_https": "https://pbs.twimg.com/media/img2.jpg"},
                    ]
                },
            }
        ]
        posts = normalize_x_posts(raw)
        assert len(posts[0].image_urls) == 2
        assert posts[0].image_urls[0] == "https://pbs.twimg.com/media/img1.jpg"

    def test_media_fallback_to_media_array(self):
        """Falls back to top-level media array when extendedEntities missing."""
        raw = [
            {
                "id": "t6",
                "text": "Fallback media",
                "author": {"username": "u"},
                "created_at": "",
                "media": [{"url": "https://example.com/img.jpg"}],
            }
        ]
        posts = normalize_x_posts(raw)
        assert posts[0].image_urls == ["https://example.com/img.jpg"]


# ---------------------------------------------------------------------------
# Facebook normalization
# ---------------------------------------------------------------------------


class TestNormalizeFacebookPosts:
    def test_basic_post(self):
        """Test with cleansyntax/facebook-profile-posts-scraper output format."""
        raw = [
            {
                "post_id": "fb123",
                "url": "https://www.facebook.com/NASA/posts/fb123",
                "message": "Rocket launch today!",
                "author": {"name": "NASA"},
                "timestamp": 1704110400,  # 2024-01-01T12:00:00Z
                "reactions_count": 500,
                "comments_count": 42,
                "reshare_count": 100,
                "image": {"uri": "https://cdn.example.com/thumb.jpg"},
            }
        ]
        posts = normalize_facebook_posts(raw)
        assert len(posts) == 1
        p = posts[0]
        assert p.id == "fb123"
        assert p.url == "https://www.facebook.com/NASA/posts/fb123"
        assert p.text == "Rocket launch today!"
        assert p.author == "NASA"
        assert p.platform == "facebook"
        assert p.image_urls == ["https://cdn.example.com/thumb.jpg"]
        assert p.engagement["likes"] == 500
        assert p.engagement["comments"] == 42
        assert p.engagement["shares"] == 100

    def test_author_from_nested_object(self):
        """Author extracted from author.name."""
        raw = [
            {
                "post_id": "fb456",
                "author": {"name": "SpaceX", "id": "123"},
                "message": "Test",
            }
        ]
        posts = normalize_facebook_posts(raw)
        assert posts[0].author == "SpaceX"

    def test_empty_author(self):
        """Empty author when author object is missing."""
        raw = [
            {
                "post_id": "fb789",
                "message": "Test",
            }
        ]
        posts = normalize_facebook_posts(raw)
        assert posts[0].author == ""

    def test_skips_items_without_post_id(self):
        """Metadata rows (profile_id resolution) are skipped."""
        raw = [
            {"profile_id": "123", "url (search term)": "https://facebook.com/NASA/"},
            {"post_id": "ok1", "message": "Has ID"},
        ]
        posts = normalize_facebook_posts(raw)
        assert len(posts) == 1
        assert posts[0].id == "ok1"

    def test_empty_input(self):
        assert normalize_facebook_posts([]) == []

    def test_album_preview_extraction(self):
        """Image URLs from album_preview array."""
        raw = [
            {
                "post_id": "fb_media",
                "message": "Photos",
                "album_preview": [
                    {"type": "photo", "image_file_uri": "https://cdn.example.com/photo1.jpg"},
                    {"type": "photo", "image_file_uri": "https://cdn.example.com/photo2.jpg"},
                ],
            }
        ]
        posts = normalize_facebook_posts(raw)
        assert len(posts[0].image_urls) == 2

    def test_single_image_and_album(self):
        """Both image.uri and album_preview are collected."""
        raw = [
            {
                "post_id": "fb_both",
                "message": "Mixed",
                "image": {"uri": "https://cdn.example.com/single.jpg"},
                "album_preview": [
                    {"type": "photo", "image_file_uri": "https://cdn.example.com/album1.jpg"},
                ],
            }
        ]
        posts = normalize_facebook_posts(raw)
        assert len(posts[0].image_urls) == 2

    def test_text_fallback_to_message_rich(self):
        """Falls back to 'message_rich' when 'message' is missing."""
        raw = [{"post_id": "fb_rich", "message_rich": "Hello **rich**"}]
        posts = normalize_facebook_posts(raw)
        assert posts[0].text == "Hello **rich**"

    def test_unix_timestamp_converted_to_iso(self):
        """Unix epoch timestamps are converted to ISO 8601."""
        raw = [
            {
                "post_id": "fb_ts",
                "message": "Test",
                "timestamp": 1704110400,
            }
        ]
        posts = normalize_facebook_posts(raw)
        assert "2024-01-01" in posts[0].timestamp

    def test_video_extraction(self):
        """Video URL extracted from video object."""
        raw = [
            {
                "post_id": "fb_vid",
                "message": "Video post",
                "video": {"url": "https://cdn.example.com/video.mp4"},
            }
        ]
        posts = normalize_facebook_posts(raw)
        assert posts[0].video_url == "https://cdn.example.com/video.mp4"


# ---------------------------------------------------------------------------
# Post diffing
# ---------------------------------------------------------------------------


def _make_post(post_id: str, platform: str = "instagram") -> NormalizedPost:
    return NormalizedPost(
        id=post_id,
        url=f"https://example.com/{post_id}",
        text="test",
        author="user",
        timestamp="2025-01-01",
        platform=platform,
    )


def _make_snapshot(post_id: str) -> PostSnapshot:
    return PostSnapshot(
        post_id=post_id,
        caption_truncated="Old caption",
        timestamp="2025-01-01",
    )


class TestIdentifyNewPosts:
    def test_all_new(self):
        posts = [_make_post("a"), _make_post("b")]
        new = identify_new_posts(posts, set())
        assert len(new) == 2

    def test_none_new(self):
        posts = [_make_post("a"), _make_post("b")]
        new = identify_new_posts(posts, {"a", "b"})
        assert len(new) == 0

    def test_partial_new(self):
        posts = [_make_post("a"), _make_post("b"), _make_post("c")]
        new = identify_new_posts(posts, {"a"})
        assert len(new) == 2
        assert {p.id for p in new} == {"b", "c"}

    def test_empty_current(self):
        new = identify_new_posts([], {"a", "b"})
        assert len(new) == 0


class TestIdentifyRemovedPosts:
    def test_none_removed(self):
        current_ids = {"a", "b"}
        snapshot = [_make_snapshot("a"), _make_snapshot("b")]
        removed = identify_removed_posts(current_ids, snapshot)
        assert len(removed) == 0

    def test_some_removed(self):
        current_ids = {"a"}
        snapshot = [_make_snapshot("a"), _make_snapshot("b"), _make_snapshot("c")]
        removed = identify_removed_posts(current_ids, snapshot)
        assert len(removed) == 2
        assert {r.post_id for r in removed} == {"b", "c"}

    def test_all_removed(self):
        current_ids = set()
        snapshot = [_make_snapshot("a")]
        removed = identify_removed_posts(current_ids, snapshot)
        assert len(removed) == 1

    def test_empty_snapshot(self):
        removed = identify_removed_posts({"a"}, [])
        assert len(removed) == 0


# ---------------------------------------------------------------------------
# Profile URL
# ---------------------------------------------------------------------------


class TestBuildProfileUrl:
    def test_instagram(self):
        url = build_profile_url("instagram", "testuser")
        assert url == "https://www.instagram.com/testuser/"

    def test_instagram_strips_at(self):
        url = build_profile_url("instagram", "@testuser")
        assert url == "https://www.instagram.com/testuser/"

    def test_x(self):
        url = build_profile_url("x", "tweetuser")
        assert url == "https://x.com/tweetuser"

    def test_x_strips_at(self):
        url = build_profile_url("x", "@tweetuser")
        assert url == "https://x.com/tweetuser"

    def test_facebook(self):
        url = build_profile_url("facebook", "NASA")
        assert url == "https://www.facebook.com/NASA/"

    def test_facebook_strips_at(self):
        url = build_profile_url("facebook", "@NASA")
        assert url == "https://www.facebook.com/NASA/"

    def test_unknown_platform(self):
        url = build_profile_url("tiktok", "user")
        assert url == ""

    def test_handle_with_spaces(self):
        url = build_profile_url("instagram", "  user  ")
        assert url == "https://www.instagram.com/user/"


# ---------------------------------------------------------------------------
# Criteria matching
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def testmatch_criteria_returns_matching_posts():
    """match_criteria returns posts with high embedding similarity to criteria."""
    posts = [
        NormalizedPost(
            id="1",
            url="https://x.com/user/status/1",
            text="New housing policy announced",
            author="user",
            timestamp="2025-01-01",
            image_urls=[],
            platform="x",
        ),
        NormalizedPost(
            id="2",
            url="https://x.com/user/status/2",
            text="Beautiful sunset today",
            author="user",
            timestamp="2025-01-01",
            image_urls=[],
            platform="x",
        ),
    ]

    with patch("app.services.social_orchestrator.generate_embedding") as mock_embed, \
         patch("app.services.social_orchestrator.generate_post_embedding") as mock_post_embed:
        # criteria embedding: unit vector along dimension 0
        mock_embed.return_value = [1.0] + [0.0] * 1535
        # post 1: identical direction → cosine similarity = 1.0 (> 0.65)
        # post 2: orthogonal → cosine similarity = 0.0 (< 0.65)
        similar_vec = [1.0] + [0.0] * 1535
        dissimilar_vec = [0.0] + [1.0] + [0.0] * 1534
        mock_post_embed.side_effect = [similar_vec, dissimilar_vec]

        from app.services.social_orchestrator import match_criteria
        matched = await match_criteria(posts, "housing policy changes", "x")

    # Only post 1 should match (cosine similarity > 0.65)
    assert len(matched) == 1
    assert matched[0].id == "1"


@pytest.mark.asyncio
async def testmatch_criteria_empty_posts():
    """match_criteria returns empty list for empty posts."""
    from app.services.social_orchestrator import match_criteria
    result = await match_criteria([], "some criteria", "instagram")
    assert result == []


@pytest.mark.asyncio
async def testmatch_criteria_empty_criteria():
    """match_criteria returns empty list for empty criteria."""
    post = NormalizedPost(
        id="1",
        url="https://x.com/user/status/1",
        text="hi",
        author="user",
        timestamp="2025-01-01",
        platform="x",
    )
    from app.services.social_orchestrator import match_criteria
    result = await match_criteria([post], "", "x")
    assert result == []


# ---------------------------------------------------------------------------
# Post removal notification
# ---------------------------------------------------------------------------


def test_identify_removed_posts_with_empty_snapshot():
    """No removals when snapshot is empty (first run)."""
    from app.services.social_orchestrator import identify_removed_posts
    result = identify_removed_posts({"post_1", "post_2"}, [])
    assert result == []
