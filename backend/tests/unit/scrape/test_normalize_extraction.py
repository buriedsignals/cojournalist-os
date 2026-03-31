"""
Tests for data extractor normalization functions (CSV-ready output).

Covers all 5 platform normalizers in app/workflows/data_extractor.py:
- normalize_apify_results (X/Twitter)
- normalize_instagram_results (Instagram)
- normalize_facebook_results (Facebook)
- normalize_tiktok_results (TikTok)
- normalize_instagram_comments (Instagram Comments)

These are pure functions — no mocking or async needed.
"""

from app.workflows.data_extractor import (
    normalize_apify_results,
    normalize_instagram_results,
    normalize_facebook_results,
    normalize_tiktok_results,
    normalize_instagram_comments,
)


# ---------------------------------------------------------------------------
# X / Twitter — normalize_apify_results
# ---------------------------------------------------------------------------


class TestNormalizeApifyResults:
    def test_basic_tweet(self):
        raw = [
            {
                "id": "t1",
                "text": "Hello world",
                "url": "https://x.com/user/status/t1",
                "created_at": "2025-01-01T00:00:00Z",
                "author": {"username": "testuser", "name": "Test User"},
                "favorite_count": 10,
                "retweet_count": 3,
                "reply_count": 1,
                "quote_count": 0,
                "lang": "en",
            }
        ]
        result = normalize_apify_results(raw)
        assert len(result) == 1
        r = result[0]
        assert r["id"] == "t1"
        assert r["text"] == "Hello world"
        assert r["author_username"] == "testuser"
        assert r["author_name"] == "Test User"
        assert r["favorite_count"] == 10
        assert r["lang"] == "en"

    def test_media_extraction(self):
        raw = [
            {
                "id": "t2",
                "text": "With media",
                "extendedEntities": {
                    "media": [
                        {"media_url_https": "https://pbs.twimg.com/img1.jpg", "type": "photo"},
                        {"media_url_https": "https://pbs.twimg.com/img2.jpg", "type": "photo"},
                    ]
                },
            }
        ]
        result = normalize_apify_results(raw)
        assert "img1.jpg" in result[0]["media_urls"]
        assert "img2.jpg" in result[0]["media_urls"]
        assert result[0]["media_type"] == "photo, photo"

    def test_media_fallback_to_media_array(self):
        raw = [{"id": "t3", "text": "Fallback", "media": [{"url": "https://example.com/vid.mp4", "type": "video"}]}]
        result = normalize_apify_results(raw)
        assert "vid.mp4" in result[0]["media_urls"]

    def test_empty_input(self):
        assert normalize_apify_results([]) == []
        assert normalize_apify_results(None) == []

    def test_non_dict_item(self):
        result = normalize_apify_results(["raw string"])
        assert result[0]["text"] == "raw string"

    def test_like_count_fallback(self):
        raw = [{"id": "t4", "text": "X", "like_count": 99}]
        result = normalize_apify_results(raw)
        assert result[0]["favorite_count"] == 99


# ---------------------------------------------------------------------------
# Instagram — normalize_instagram_results
# ---------------------------------------------------------------------------


class TestNormalizeInstagramResults:
    def test_basic_post(self):
        raw = [
            {
                "id": "ig1",
                "code": "ABC",
                "url": "https://www.instagram.com/p/ABC/",
                "createdAt": "2025-01-01T00:00:00Z",
                "caption": "Hello Instagram",
                "likeCount": 42,
                "commentCount": 5,
                "owner": {"username": "iguser", "fullName": "IG User", "followerCount": 1000},
                "image": {"url": "https://cdn.example.com/img.jpg"},
            }
        ]
        result = normalize_instagram_results(raw)
        assert len(result) == 1
        r = result[0]
        assert r["id"] == "ig1"
        assert r["caption"] == "Hello Instagram"
        assert r["owner_username"] == "iguser"
        assert r["owner_name"] == "IG User"
        assert r["owner_followers"] == 1000
        assert r["image_urls"] == "https://cdn.example.com/img.jpg"
        assert r["like_count"] == 42

    def test_carousel_images(self):
        raw = [
            {
                "id": "ig2",
                "images": [
                    {"url": "https://cdn.example.com/1.jpg"},
                    {"url": "https://cdn.example.com/2.jpg"},
                ],
            }
        ]
        result = normalize_instagram_results(raw)
        assert "1.jpg" in result[0]["image_urls"]
        assert "2.jpg" in result[0]["image_urls"]

    def test_video_fields(self):
        raw = [
            {
                "id": "ig3",
                "isVideo": True,
                "video": {"url": "https://cdn.example.com/vid.mp4", "duration": 30, "playCount": 5000},
            }
        ]
        result = normalize_instagram_results(raw)
        assert result[0]["video_url"] == "https://cdn.example.com/vid.mp4"
        assert result[0]["video_duration"] == 30
        assert result[0]["video_play_count"] == 5000
        assert result[0]["is_video"] is True

    def test_empty_input(self):
        assert normalize_instagram_results([]) == []
        assert normalize_instagram_results(None) == []

    def test_location_extraction(self):
        raw = [{"id": "ig4", "location": {"name": "Central Park"}}]
        result = normalize_instagram_results(raw)
        assert result[0]["location_name"] == "Central Park"


# ---------------------------------------------------------------------------
# Facebook — normalize_facebook_results
# ---------------------------------------------------------------------------


class TestNormalizeFacebookResults:
    def test_basic_post(self):
        raw = [
            {
                "post_id": "fb1",
                "message": "Hello Facebook",
                "url": "https://facebook.com/post/fb1",
                "timestamp": 1704110400,
                "author": {"name": "FB User"},
                "reactions_count": 20,
                "comments_count": 3,
                "reshare_count": 1,
            }
        ]
        result = normalize_facebook_results(raw)
        assert len(result) == 1
        r = result[0]
        assert r["id"] == "fb1"
        assert r["text"] == "Hello Facebook"
        assert r["author_name"] == "FB User"
        assert r["like_count"] == 20
        assert "2024-01-01" in r["created_at"]

    def test_album_preview(self):
        raw = [
            {
                "post_id": "fb2",
                "message": "Album",
                "album_preview": [
                    {"image_file_uri": "https://cdn.example.com/p1.jpg"},
                    {"image_file_uri": "https://cdn.example.com/p2.jpg"},
                ],
            }
        ]
        result = normalize_facebook_results(raw)
        assert "p1.jpg" in result[0]["media_urls"]
        assert "p2.jpg" in result[0]["media_urls"]

    def test_single_image_and_album(self):
        raw = [
            {
                "post_id": "fb3",
                "message": "Both",
                "image": {"uri": "https://cdn.example.com/single.jpg"},
                "album_preview": [{"image_file_uri": "https://cdn.example.com/album.jpg"}],
            }
        ]
        result = normalize_facebook_results(raw)
        assert "single.jpg" in result[0]["media_urls"]
        assert "album.jpg" in result[0]["media_urls"]

    def test_message_rich_fallback(self):
        raw = [{"post_id": "fb4", "message_rich": "Rich **text**"}]
        result = normalize_facebook_results(raw)
        assert result[0]["text"] == "Rich **text**"

    def test_skips_metadata_rows(self):
        raw = [{"profile_id": "12345"}, {"post_id": "fb5", "message": "Real"}]
        result = normalize_facebook_results(raw)
        assert len(result) == 1
        assert result[0]["id"] == "fb5"

    def test_skips_error_items(self):
        raw = [{"post_id": "fb6", "error": "Rate limited"}]
        result = normalize_facebook_results(raw)
        assert len(result) == 0

    def test_empty_input(self):
        assert normalize_facebook_results([]) == []
        assert normalize_facebook_results(None) == []


# ---------------------------------------------------------------------------
# TikTok — normalize_tiktok_results
# ---------------------------------------------------------------------------


class TestNormalizeTikTokResults:
    def test_basic_video(self):
        raw = [
            {
                "aweme_id": "730000",
                "desc": "TikTok video about climate",
                "create_time": 1704110400,
                "share_url": "https://www.tiktok.com/@user/video/730000",
                "author": {"unique_id": "testuser", "nickname": "Test User"},
                "video": {
                    "cover": {"url_list": ["https://cdn.example.com/cover.jpg"]},
                    "play_addr": {"url_list": ["https://cdn.example.com/video.mp4"]},
                    "duration": 15,
                },
            }
        ]
        result = normalize_tiktok_results(raw)
        assert len(result) == 1
        r = result[0]
        assert r["id"] == "730000"
        assert r["description"] == "TikTok video about climate"
        assert r["author_username"] == "testuser"
        assert r["author_name"] == "Test User"
        assert r["cover_url"] == "https://cdn.example.com/cover.jpg"
        assert r["video_url"] == "https://cdn.example.com/video.mp4"
        assert r["video_duration"] == 15
        assert "2024-01-01" in r["created_at"]

    def test_url_fallback_construction(self):
        raw = [
            {
                "aweme_id": "456",
                "desc": "No share URL",
                "create_time": 1704110400,
                "author": {"unique_id": "myuser"},
                "video": {"cover": {}, "play_addr": {}},
            }
        ]
        result = normalize_tiktok_results(raw)
        assert result[0]["url"] == "https://www.tiktok.com/@myuser/video/456"

    def test_content_desc_fallback(self):
        raw = [
            {
                "aweme_id": "111",
                "content_desc": "Fallback description",
                "create_time": 1704110400,
                "author": {"unique_id": "user"},
                "video": {"cover": {}, "play_addr": {}},
            }
        ]
        result = normalize_tiktok_results(raw)
        assert result[0]["description"] == "Fallback description"

    def test_skips_items_without_id(self):
        raw = [{"desc": "No ID", "author": {"unique_id": "user"}}]
        result = normalize_tiktok_results(raw)
        assert len(result) == 0

    def test_empty_cover_and_play(self):
        raw = [
            {
                "aweme_id": "789",
                "desc": "Minimal",
                "create_time": 1704110400,
                "author": {"unique_id": "user"},
                "video": {"cover": {"url_list": []}, "play_addr": {"url_list": []}},
            }
        ]
        result = normalize_tiktok_results(raw)
        assert result[0]["cover_url"] is None
        assert result[0]["video_url"] is None

    def test_empty_input(self):
        assert normalize_tiktok_results([]) == []
        assert normalize_tiktok_results(None) == []


# ---------------------------------------------------------------------------
# Instagram Comments — normalize_instagram_comments
# ---------------------------------------------------------------------------


class TestNormalizeInstagramComments:
    def test_basic_comment(self):
        raw = [
            {
                "id": "c1",
                "text": "Great post!",
                "ownerUsername": "commenter",
                "timestamp": "2025-01-01T00:00:00Z",
                "likesCount": 5,
            }
        ]
        result = normalize_instagram_comments(raw)
        assert len(result) == 1
        r = result[0]
        assert r["id"] == "c1"
        assert r["text"] == "Great post!"
        assert r["author_username"] == "commenter"
        assert r["like_count"] == 5
        assert r["is_reply"] is False

    def test_reply_comment(self):
        raw = [{"id": "c2", "text": "Reply", "parentId": "c1"}]
        result = normalize_instagram_comments(raw)
        assert result[0]["is_reply"] is True
        assert result[0]["parent_id"] == "c1"

    def test_username_fallbacks(self):
        raw = [{"id": "c3", "text": "Test", "owner_username": "alt_field"}]
        result = normalize_instagram_comments(raw)
        assert result[0]["author_username"] == "alt_field"

    def test_skips_error_items(self):
        raw = [{"id": "c4", "error": "Post not found"}]
        result = normalize_instagram_comments(raw)
        assert len(result) == 0

    def test_skips_request_error_items(self):
        raw = [{"id": "c5", "requestErrorMessages": ["Rate limited"]}]
        result = normalize_instagram_comments(raw)
        assert len(result) == 0

    def test_empty_input(self):
        assert normalize_instagram_comments([]) == []
        assert normalize_instagram_comments(None) == []
