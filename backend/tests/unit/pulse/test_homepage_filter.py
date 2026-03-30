"""Tests for is_index_or_homepage() URL filter."""
import pytest
from app.services.news_utils import is_index_or_homepage


class TestHomepageFilter:
    """is_index_or_homepage() rejects bare homepages and section landing URLs."""

    def test_bare_homepage(self):
        assert is_index_or_homepage("https://example.com/") is True

    def test_bare_homepage_no_trailing_slash(self):
        assert is_index_or_homepage("https://example.com") is True

    def test_blog_landing(self):
        assert is_index_or_homepage("https://example.com/blog") is True

    def test_news_landing(self):
        assert is_index_or_homepage("https://example.com/news") is True

    def test_articles_landing(self):
        assert is_index_or_homepage("https://example.com/articles") is True

    def test_archive_landing(self):
        assert is_index_or_homepage("https://example.com/archive") is True

    def test_category_landing(self):
        assert is_index_or_homepage("https://example.com/category") is True

    def test_blog_article_passes(self):
        assert is_index_or_homepage("https://example.com/blog/my-article") is False

    def test_date_path_passes(self):
        assert is_index_or_homepage("https://example.com/2024/03/story") is False

    def test_deep_path_passes(self):
        assert is_index_or_homepage("https://example.com/section/subsection/page") is False

    def test_news_article_passes(self):
        assert is_index_or_homepage("https://news.ch/article/12345") is False

    def test_case_insensitive(self):
        assert is_index_or_homepage("https://example.com/Blog") is True
        assert is_index_or_homepage("https://example.com/NEWS") is True
