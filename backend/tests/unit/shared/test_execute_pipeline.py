"""
Tests for the shared execute pipeline (run_post_orchestrator_pipeline).

Verifies:
- PipelineContext defaults skip_unit_extraction to False
- skip_unit_extraction=True skips process_results but still stores EXEC# record
- skip_unit_extraction=False calls process_results normally
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.execute_pipeline import PipelineContext, run_post_orchestrator_pipeline
from app.services.atomic_unit_service import ProcessingResult


# Patch targets (module where names are looked up at runtime)
_EP = "app.services.execute_pipeline"


def _make_ctx(skip_unit_extraction=False, skip_credit_charge=False):
    """Build a PipelineContext with sensible defaults."""
    return PipelineContext(
        user_id="user_123",
        scraper_name="test-scout",
        scout_type="pulse",
        location=None,
        topic="test topic",
        preferred_language="en",
        start_time=1000.0,
        credit_cost=7,
        skip_credit_charge=skip_credit_charge,
        skip_unit_extraction=skip_unit_extraction,
    )


def _processing_result(new_facts=None, duplicate_facts=None, all_duplicates=False):
    return ProcessingResult(
        new_facts=new_facts or [],
        duplicate_facts=duplicate_facts or [],
        all_duplicates=all_duplicates,
    )


class TestSkipUnitExtraction:
    """Tests for skip_unit_extraction behavior in the shared pipeline."""

    def test_pipeline_context_defaults_false(self):
        """PipelineContext without skip_unit_extraction has it as False."""
        ctx = PipelineContext(
            user_id="user_123",
            scraper_name="test-scout",
            scout_type="pulse",
            location=None,
            topic=None,
            preferred_language="en",
            start_time=1000.0,
            credit_cost=7,
        )
        assert ctx.skip_unit_extraction is False

    @pytest.mark.asyncio
    async def test_pipeline_skips_process_results_when_true(self):
        """When skip_unit_extraction=True, process_results is NOT called but EXEC# record IS stored."""
        mock_atomic = MagicMock()
        mock_atomic.process_results = AsyncMock()

        mock_exec_dedup = MagicMock()
        mock_exec_dedup.store_execution = AsyncMock(return_value={})

        mock_send_notification = AsyncMock(return_value=False)

        ctx = _make_ctx(skip_unit_extraction=True)

        with patch(f"{_EP}.atomic_unit_service", mock_atomic), \
             patch(f"{_EP}.exec_dedup_service", mock_exec_dedup), \
             patch(f"{_EP}.decrement_credit", AsyncMock()), \
             patch(f"{_EP}.log_scout_execution", MagicMock()):

            result = await run_post_orchestrator_pipeline(
                articles=[{"title": "Test", "summary": "Summary", "url": "http://test.com", "content": "Content"}],
                ctx=ctx,
                recent_facts=[],
                user_email="test@test.com",
                send_notification=mock_send_notification,
            )

        # process_results should NOT have been called
        mock_atomic.process_results.assert_not_awaited()

        # EXEC# record should still be stored
        mock_exec_dedup.store_execution.assert_awaited_once()
        store_kwargs = mock_exec_dedup.store_execution.call_args.kwargs
        assert store_kwargs["is_duplicate"] is True
        assert store_kwargs["summary_text"] == "No new findings"

        # Result should indicate all duplicates (early return path)
        assert result.all_duplicates is True

    @pytest.mark.asyncio
    async def test_pipeline_calls_process_results_when_false(self):
        """When skip_unit_extraction=False (default), process_results IS called."""
        mock_atomic = MagicMock()
        mock_atomic.process_results = AsyncMock(
            return_value=_processing_result(
                new_facts=[{"statement": "New finding", "source_url": "http://test.com"}],
            )
        )

        mock_exec_dedup = MagicMock()
        mock_exec_dedup.generate_summary_from_facts = AsyncMock(return_value="New discovery")
        mock_exec_dedup.store_execution = AsyncMock(return_value={})

        mock_send_notification = AsyncMock(return_value=True)

        ctx = _make_ctx(skip_unit_extraction=False)

        with patch(f"{_EP}.atomic_unit_service", mock_atomic), \
             patch(f"{_EP}.exec_dedup_service", mock_exec_dedup), \
             patch(f"{_EP}.decrement_credit", AsyncMock()), \
             patch(f"{_EP}.log_scout_execution", MagicMock()):

            result = await run_post_orchestrator_pipeline(
                articles=[{"title": "Test", "summary": "Summary", "url": "http://test.com", "content": "Content"}],
                ctx=ctx,
                recent_facts=[],
                user_email="test@test.com",
                send_notification=mock_send_notification,
            )

        # process_results SHOULD have been called
        mock_atomic.process_results.assert_awaited_once()

        # Result should NOT be all duplicates
        assert result.all_duplicates is False

