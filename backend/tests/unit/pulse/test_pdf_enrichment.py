"""Tests for PDF OCR enrichment in the pulse pipeline."""

import pytest
from unittest.mock import AsyncMock, patch

from app.services.news_utils import (
    extract_date_from_pdf_text,
    enrich_pdf_results,
    MAX_PDFS_PER_SEARCH,
)


# =============================================================================
# extract_date_from_pdf_text
# =============================================================================


class TestExtractDateFromPdfText:
    """Test date extraction from PDF text content."""

    def test_iso_date(self):
        text = "Report published on 2026-03-06 for the council."
        assert extract_date_from_pdf_text(text) == "2026-03-06"

    def test_english_date(self):
        text = "Published: March 6, 2026\nSome content follows."
        assert extract_date_from_pdf_text(text) == "March 6, 2026"

    def test_english_date_abbreviated(self):
        text = "Date: Jan 15, 2026"
        assert extract_date_from_pdf_text(text) == "Jan 15, 2026"

    def test_german_date(self):
        text = "Protokoll vom 28. November 2026\nTagesordnung..."
        assert extract_date_from_pdf_text(text) == "28. November 2026"

    def test_german_month_maerz(self):
        text = "Sitzung vom 5. März 2026"
        assert extract_date_from_pdf_text(text) == "5. März 2026"

    def test_french_date(self):
        text = "Rapport du 15 janvier 2026"
        assert extract_date_from_pdf_text(text) == "15 janvier 2026"

    def test_swedish_date(self):
        text = "Publicerad 10 mars 2026"
        assert extract_date_from_pdf_text(text) == "10 mars 2026"

    def test_dot_separated_date(self):
        text = "Datum: 06.03.2026\nInhalt..."
        assert extract_date_from_pdf_text(text) == "06.03.2026"

    def test_slash_separated_date(self):
        text = "Date: 03/06/2026"
        assert extract_date_from_pdf_text(text) == "03/06/2026"

    def test_european_date_no_dot(self):
        text = "Meeting on 6 March 2026"
        assert extract_date_from_pdf_text(text) == "6 March 2026"

    def test_no_date_found(self):
        text = "This document has no date references at all."
        assert extract_date_from_pdf_text(text) is None

    def test_old_date_still_extracted(self):
        """Dates outside 2020-2039 range are not matched."""
        text = "Historical record from 2019-05-01"
        assert extract_date_from_pdf_text(text) is None

    def test_respects_max_chars(self):
        """Date beyond max_chars is not found."""
        text = "x" * 3000 + "2026-03-06"
        assert extract_date_from_pdf_text(text, max_chars=2000) is None

    def test_first_date_wins(self):
        """Returns the first date found in the text."""
        text = "Published 2026-01-15. Updated 2026-03-06."
        assert extract_date_from_pdf_text(text) == "2026-01-15"


# =============================================================================
# enrich_pdf_results
# =============================================================================


class TestEnrichPdfResults:
    """Test the PDF enrichment pipeline function."""

    @pytest.mark.asyncio
    async def test_no_pdfs_returns_unchanged(self):
        """When no PDF URLs exist, results pass through unchanged."""
        results = [
            {"url": "https://example.com/article", "title": "Test", "description": "Desc"},
        ]
        mock_tools = AsyncMock()
        enriched = await enrich_pdf_results(results, mock_tools)
        assert enriched == results
        mock_tools.scrape_pdf.assert_not_called()

    @pytest.mark.asyncio
    async def test_pdf_enriches_date_from_metadata(self):
        """PDF with metadata publishedDate enriches the article."""
        results = [
            {"url": "https://gov.ch/report.pdf", "title": "Report", "description": "", "date": None},
        ]
        mock_tools = AsyncMock()
        mock_tools.scrape_pdf.return_value = {
            "markdown": "Council meeting protocol...",
            "metadata": {"publishedDate": "2026-03-01", "title": "Council Report"},
        }

        enriched = await enrich_pdf_results(results, mock_tools)
        assert enriched[0]["date"] == "2026-03-01"
        mock_tools.scrape_pdf.assert_called_once()

    @pytest.mark.asyncio
    async def test_pdf_enriches_date_from_text(self):
        """When metadata has no date, extracts from text content."""
        results = [
            {"url": "https://gov.ch/report.pdf", "title": "Report", "description": "", "date": None},
        ]
        mock_tools = AsyncMock()
        mock_tools.scrape_pdf.return_value = {
            "markdown": "Protokoll vom 28. November 2026\nTagesordnung...",
            "metadata": {},
        }

        enriched = await enrich_pdf_results(results, mock_tools)
        assert enriched[0]["date"] == "28. November 2026"

    @pytest.mark.asyncio
    async def test_pdf_enriches_description(self):
        """Short descriptions are replaced with extracted text."""
        results = [
            {"url": "https://gov.ch/report.pdf", "title": "Report", "description": "PDF", "date": "2026-01-01"},
        ]
        mock_tools = AsyncMock()
        mock_tools.scrape_pdf.return_value = {
            "markdown": "This is a detailed council meeting protocol discussing budget allocations.",
            "metadata": {},
        }

        enriched = await enrich_pdf_results(results, mock_tools)
        assert "detailed council meeting" in enriched[0]["description"]

    @pytest.mark.asyncio
    async def test_existing_date_not_overwritten(self):
        """Articles that already have dates are not overwritten."""
        results = [
            {"url": "https://gov.ch/report.pdf", "title": "Report", "description": "", "date": "2026-02-15"},
        ]
        mock_tools = AsyncMock()
        mock_tools.scrape_pdf.return_value = {
            "markdown": "Published 2026-03-01",
            "metadata": {"publishedDate": "2026-03-01"},
        }

        enriched = await enrich_pdf_results(results, mock_tools)
        assert enriched[0]["date"] == "2026-02-15"  # Unchanged

    @pytest.mark.asyncio
    async def test_caps_pdf_count(self):
        """Only scrapes up to MAX_PDFS_PER_SEARCH PDFs."""
        results = [
            {"url": f"https://gov.ch/report{i}.pdf", "title": f"Report {i}", "description": "", "date": None}
            for i in range(10)
        ]
        mock_tools = AsyncMock()
        mock_tools.scrape_pdf.return_value = {"markdown": "Content", "metadata": {}}

        await enrich_pdf_results(results, mock_tools, max_pdfs=3)
        assert mock_tools.scrape_pdf.call_count == 3

    @pytest.mark.asyncio
    async def test_scrape_failure_handled_gracefully(self):
        """Failed PDF scrapes don't crash the pipeline."""
        results = [
            {"url": "https://gov.ch/report.pdf", "title": "Report", "description": "Desc", "date": None},
            {"url": "https://example.com/article", "title": "Normal", "description": "Normal desc", "date": "2026-01-01"},
        ]
        mock_tools = AsyncMock()
        mock_tools.scrape_pdf.side_effect = Exception("Timeout")

        enriched = await enrich_pdf_results(results, mock_tools)
        assert len(enriched) == 2
        assert enriched[0]["date"] is None  # Not enriched due to failure

    @pytest.mark.asyncio
    async def test_error_response_handled(self):
        """Error dict from scrape_pdf is handled gracefully."""
        results = [
            {"url": "https://gov.ch/report.pdf", "title": "Report", "description": "", "date": None},
        ]
        mock_tools = AsyncMock()
        mock_tools.scrape_pdf.return_value = {"error": "PDF scrape failed: 402"}

        enriched = await enrich_pdf_results(results, mock_tools)
        assert enriched[0]["date"] is None

    @pytest.mark.asyncio
    async def test_mixed_pdf_and_html_results(self):
        """Only PDF URLs are scraped; HTML articles pass through."""
        results = [
            {"url": "https://news.com/article", "title": "News", "description": "News desc", "date": "2026-03-01"},
            {"url": "https://gov.ch/report.pdf", "title": "Report", "description": "", "date": None},
            {"url": "https://blog.com/post", "title": "Blog", "description": "Blog desc", "date": "2026-02-28"},
        ]
        mock_tools = AsyncMock()
        mock_tools.scrape_pdf.return_value = {
            "markdown": "Official report content 2026-01-15",
            "metadata": {},
        }

        enriched = await enrich_pdf_results(results, mock_tools)
        assert mock_tools.scrape_pdf.call_count == 1  # Only the PDF
        assert enriched[0]["date"] == "2026-03-01"  # HTML unchanged
        assert enriched[1]["date"] == "2026-01-15"  # PDF enriched
        assert enriched[2]["date"] == "2026-02-28"  # HTML unchanged

    @pytest.mark.asyncio
    async def test_long_description_not_overwritten(self):
        """Descriptions >= 50 chars are kept even when PDF has content."""
        original_desc = "This is a sufficiently long description that should not be replaced by PDF text"
        results = [
            {"url": "https://gov.ch/report.pdf", "title": "Report", "description": original_desc, "date": None},
        ]
        mock_tools = AsyncMock()
        mock_tools.scrape_pdf.return_value = {
            "markdown": "Different PDF content here",
            "metadata": {},
        }

        enriched = await enrich_pdf_results(results, mock_tools)
        assert enriched[0]["description"] == original_desc
