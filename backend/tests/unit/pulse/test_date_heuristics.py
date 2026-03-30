"""Unit tests for URL/title date heuristics: extract_content_year and is_stale_content."""
import pytest
from unittest.mock import patch
from datetime import datetime


class TestExtractContentYear:

    def test_year_in_url_path_segment(self):
        from app.services.news_utils import extract_content_year
        assert extract_content_year(url="https://example.com/2023/report.pdf") == 2023

    def test_year_in_url_underscore_date(self):
        from app.services.news_utils import extract_content_year
        assert extract_content_year(url="https://stadt.ch/protokoll_28_11_2023.pdf") == 2023

    def test_year_in_url_hyphen_date(self):
        from app.services.news_utils import extract_content_year
        assert extract_content_year(url="https://example.com/report-2024-03-15.pdf") == 2024

    def test_year_in_title(self):
        from app.services.news_utils import extract_content_year
        assert extract_content_year(title="Budget 2024 approved") == 2024

    def test_year_in_title_only(self):
        from app.services.news_utils import extract_content_year
        assert extract_content_year(url="https://example.com/page", title="Annual Report 2022") == 2022

    def test_no_year_found(self):
        from app.services.news_utils import extract_content_year
        assert extract_content_year(url="https://example.com/page", title="Some article") is None

    def test_no_year_empty_inputs(self):
        from app.services.news_utils import extract_content_year
        assert extract_content_year() is None

    def test_ignores_port_numbers(self):
        from app.services.news_utils import extract_content_year
        # :2024 is a port number, should not be extracted
        assert extract_content_year(url="https://example.com:2024/page") is None

    def test_ignores_large_numeric_ids(self):
        from app.services.news_utils import extract_content_year
        # 4989550 contains 2005 as substring but is a large ID, not a year
        assert extract_content_year(url="https://example.com/article/4989550") is None

    def test_ignores_five_digit_numbers(self):
        from app.services.news_utils import extract_content_year
        assert extract_content_year(url="https://example.com/id/12024") is None

    def test_prefers_most_recent_year(self):
        from app.services.news_utils import extract_content_year
        assert extract_content_year(
            url="https://example.com/2021/archive",
            title="Updated for 2023"
        ) == 2023

    def test_multiple_years_in_url(self):
        from app.services.news_utils import extract_content_year
        assert extract_content_year(url="https://example.com/2020/to/2022/report") == 2022

    def test_url_path_only_not_domain(self):
        """Years in domain should not be matched (uses urlparse path)."""
        from app.services.news_utils import extract_content_year
        # Year only in path+query, not in domain itself
        assert extract_content_year(url="https://example.com/news/2025/article") == 2025

    def test_year_2000_boundary(self):
        from app.services.news_utils import extract_content_year
        assert extract_content_year(title="Report from 2000") == 2000

    def test_year_2029_boundary(self):
        from app.services.news_utils import extract_content_year
        assert extract_content_year(title="Projection for 2029") == 2029


class TestIsStaleContent:

    @patch("app.services.news_utils.datetime")
    def test_old_year_is_stale(self, mock_dt):
        from app.services.news_utils import is_stale_content
        mock_dt.now.return_value = datetime(2026, 3, 6)
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
        assert is_stale_content(url="https://example.com/2023/report.pdf") is True

    @patch("app.services.news_utils.datetime")
    def test_recent_year_not_stale(self, mock_dt):
        from app.services.news_utils import is_stale_content
        mock_dt.now.return_value = datetime(2026, 3, 6)
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
        assert is_stale_content(url="https://example.com/2026/news.html") is False

    @patch("app.services.news_utils.datetime")
    def test_previous_year_not_stale_default(self, mock_dt):
        from app.services.news_utils import is_stale_content
        mock_dt.now.return_value = datetime(2026, 3, 6)
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
        # 2025 is within 1-year window from 2026
        assert is_stale_content(url="https://example.com/2025/report") is False

    @patch("app.services.news_utils.datetime")
    def test_no_year_not_stale(self, mock_dt):
        from app.services.news_utils import is_stale_content
        mock_dt.now.return_value = datetime(2026, 3, 6)
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
        # No year detected → cannot determine staleness → False
        assert is_stale_content(url="https://example.com/article") is False

    @patch("app.services.news_utils.datetime")
    def test_custom_max_age(self, mock_dt):
        from app.services.news_utils import is_stale_content
        mock_dt.now.return_value = datetime(2026, 3, 6)
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
        # 2024 is 2 years old, with max_age_years=2 it should NOT be stale
        assert is_stale_content(url="https://example.com/2024/report", max_age_years=2) is False
        # 2023 is 3 years old, with max_age_years=2 it IS stale
        assert is_stale_content(url="https://example.com/2023/report", max_age_years=2) is True

    @patch("app.services.news_utils.datetime")
    def test_stale_from_title(self, mock_dt):
        from app.services.news_utils import is_stale_content
        mock_dt.now.return_value = datetime(2026, 3, 6)
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
        assert is_stale_content(title="Schaffhausen council protocol 2022") is True
