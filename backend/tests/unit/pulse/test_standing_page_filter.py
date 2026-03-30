"""Tests for is_likely_standing_page() URL filter."""
import pytest
from app.services.news_utils import is_likely_standing_page


class TestStandingPageFilter:
    """is_likely_standing_page() rejects institutional/section pages."""

    # --- Should reject (standing pages) ---

    def test_gov_mayor_page(self):
        assert is_likely_standing_page("https://www.baltimorecity.gov/mayor") is True

    def test_gov_office_landing(self):
        assert is_likely_standing_page("https://www.baltimorecity.gov/mogr") is True

    def test_gov_news_media_section(self):
        assert is_likely_standing_page("https://www.baltimorecity.gov/mayor/news-media") is True

    def test_danish_agenda_index(self):
        assert is_likely_standing_page("https://www.kk.dk/dagsordener-og-referater") is True

    def test_danish_agenda_subpage(self):
        assert is_likely_standing_page("https://www.kk.dk/dagsordener-og-referater/Borgerrepresentationen") is True

    def test_swedish_stats_page(self):
        assert is_likely_standing_page("https://malmo.se/Fakta-och-statistik/Bostader-och-hemloshet.html") is True

    def test_aggregation_page(self):
        assert is_likely_standing_page("https://bidmalmo.se/fastighetsnytt/") is True

    def test_about_page(self):
        assert is_likely_standing_page("https://example.gov/about") is True

    def test_department_page(self):
        assert is_likely_standing_page("https://city.gov/public-works/transportation") is True

    # --- Should pass (real articles) ---

    def test_article_with_numeric_id(self):
        assert is_likely_standing_page("https://stadt-schaffhausen.ch/medienmitteilungen/2502601") is False

    def test_article_with_date_path(self):
        assert is_likely_standing_page("https://www.baltimoresun.com/2026/02/25/scott-p-cards-violating/") is False

    def test_deep_path_article(self):
        assert is_likely_standing_page("https://nournews.ir/fa/news/247324/article-slug") is False

    def test_article_with_id_in_slug(self):
        assert is_likely_standing_page("https://schaffhausen24.ch/articles/364904-schweizweit-boomen") is False

    def test_long_slug_article(self):
        """Article slugs generated from titles are typically > 40 chars."""
        assert is_likely_standing_page(
            "https://folkeskolen.dk/seneste-nyt/byraad-tvinges-til-at-omgoere-beslutning-om-store-boernehaveklasser"
        ) is False

    def test_press_release_with_id(self):
        assert is_likely_standing_page(
            "https://www.mynewsdesk.com/se/malmo/pressreleases/ny-markanvisningspolicy-2984845"
        ) is False

    def test_pdf_with_date(self):
        assert is_likely_standing_page(
            "https://static.spokanecity.org/documents/bcc/agendas/2026/03/pccrs-agenda-2026-03-05.pdf"
        ) is False

    def test_three_segment_path(self):
        """Paths with 3+ segments are never flagged."""
        assert is_likely_standing_page("https://example.com/section/sub/page") is False

    def test_bare_homepage_not_caught(self):
        """Bare homepages are handled by is_index_or_homepage, not here."""
        assert is_likely_standing_page("https://example.com/") is False
        assert is_likely_standing_page("https://example.com") is False

    def test_digit_in_first_segment(self):
        assert is_likely_standing_page("https://example.com/news2026/updates") is False

    def test_year_in_path(self):
        assert is_likely_standing_page("https://example.com/2026/report") is False
