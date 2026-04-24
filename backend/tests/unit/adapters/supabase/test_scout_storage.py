"""Tests for SupabaseScoutStorage."""

import uuid
from datetime import datetime as dt
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.adapters.supabase.scout_storage import SupabaseScoutStorage


@pytest.fixture
def mock_pool():
    pool = AsyncMock()
    return pool


@pytest.fixture
def storage(mock_pool):
    with patch("app.adapters.supabase.scout_storage.get_pool", return_value=mock_pool):
        s = SupabaseScoutStorage()
        s.pool = mock_pool
    return s


class TestCreateScout:
    @pytest.mark.asyncio
    async def test_creates_scout_and_returns_dict(self, storage, mock_pool):
        scout_id = uuid.uuid4()
        mock_pool.fetchrow = AsyncMock(return_value={
            "id": scout_id,
            "user_id": uuid.uuid4(),
            "name": "my-scout",
            "type": "beat",
            "criteria": "local news",
            "preferred_language": "en",
            "regularity": "daily",
            "schedule_cron": "0 8 * * *",
            "schedule_timezone": "UTC",
            "topic": None,
            "url": None,
            "provider": None,
            "source_mode": "reliable",
            "excluded_domains": None,
            "platform": None,
            "profile_handle": None,
            "monitor_mode": None,
            "track_removals": False,
            "root_domain": None,
            "tracked_urls": None,
            "processed_pdf_urls": None,
            "location": None,
            "config": {},
            "is_active": True,
            "consecutive_failures": 0,
            "baseline_established_at": None,
            "created_at": "2026-03-29T10:00:00+00:00",
            "updated_at": "2026-03-29T10:00:00+00:00",
        })

        result = await storage.create_scout("user-1", {
            "name": "my-scout",
            "type": "beat",
            "criteria": "local news",
            "regularity": "daily",
            "schedule_cron": "0 8 * * *",
            "source_mode": "reliable",
        })

        assert result["name"] == "my-scout"
        assert result["type"] == "beat"
        mock_pool.fetchrow.assert_called_once()


class TestCreateScoutFieldMapping:
    """Tests that DynamoDB-style field names are translated to PostgreSQL columns."""

    @pytest.mark.asyncio
    async def test_translates_dynamo_field_names(self, storage, mock_pool):
        """#30: ScheduleService passes DynamoDB names, adapter should translate."""
        mock_pool.fetchrow = AsyncMock(return_value={
            "id": uuid.uuid4(), "user_id": uuid.uuid4(),
            "name": "my-scout", "type": "beat",
            "schedule_cron": "0 8 * * *", "schedule_timezone": "UTC",
        })

        # Pass DynamoDB-style names (what ScheduleService sends)
        await storage.create_scout("user-1", {
            "scraper_name": "my-scout",  # DynamoDB name -> should become "name"
            "scout_type": "beat",       # DynamoDB name -> should become "type"
            "cron_expression": "0 8 * * *",  # -> "schedule_cron"
            "timezone": "UTC",            # -> "schedule_timezone"
            "regularity": "daily",
        })

        # Verify the SQL uses PostgreSQL column names (quoted)
        call_args = mock_pool.fetchrow.call_args
        sql = call_args[0][0]
        assert '"name"' in sql  # Quoted PostgreSQL name
        assert '"type"' in sql  # Quoted reserved word
        assert 'scraper_name' not in sql  # Not the DynamoDB name
        assert 'scout_type' not in sql.split('VALUES')[0]  # Not in column list

    @pytest.mark.asyncio
    async def test_filters_empty_strings(self, storage, mock_pool):
        """#32: Empty strings should be filtered out before INSERT."""
        mock_pool.fetchrow = AsyncMock(return_value={
            "id": uuid.uuid4(), "name": "test", "type": "beat",
        })

        await storage.create_scout("user-1", {
            "name": "test",
            "type": "beat",
            "criteria": "",  # Empty string - should be filtered
            "topic": "",     # Empty string - should be filtered
            "regularity": "daily",
        })

        call_args = mock_pool.fetchrow.call_args
        sql = call_args[0][0]
        values = call_args[0][1:]
        # Empty strings should not appear in the values
        assert "" not in values

    @pytest.mark.asyncio
    async def test_quotes_all_column_names(self, storage, mock_pool):
        """#41: All column names must be quoted to handle reserved words like 'type'."""
        mock_pool.fetchrow = AsyncMock(return_value={
            "id": uuid.uuid4(), "name": "test", "type": "web",
        })

        await storage.create_scout("user-1", {
            "name": "test",
            "type": "web",
            "url": "https://example.com",
        })

        call_args = mock_pool.fetchrow.call_args
        sql = call_args[0][0]
        # Column names in INSERT should be quoted
        assert '"user_id"' in sql
        assert '"name"' in sql
        assert '"type"' in sql

    @pytest.mark.asyncio
    async def test_serializes_jsonb_fields(self, storage, mock_pool):
        """JSONB dict values should be serialized to JSON strings."""
        mock_pool.fetchrow = AsyncMock(return_value={
            "id": uuid.uuid4(), "name": "test", "type": "beat",
            "location": '{"lat": 40.7, "lng": -74.0}',
        })

        await storage.create_scout("user-1", {
            "name": "test",
            "type": "beat",
            "location": {"lat": 40.7, "lng": -74.0},
        })

        call_args = mock_pool.fetchrow.call_args
        values = call_args[0][1:]
        # Find the location value - should be a JSON string, not a dict
        json_values = [v for v in values if isinstance(v, str) and "lat" in str(v)]
        assert len(json_values) == 1


class TestGetScout:
    @pytest.mark.asyncio
    async def test_returns_scout_when_found(self, storage, mock_pool):
        mock_pool.fetchrow = AsyncMock(return_value={
            "id": uuid.uuid4(),
            "name": "test-scout",
            "type": "web",
            "is_active": True,
        })

        result = await storage.get_scout("user-1", "test-scout")
        assert result["name"] == "test-scout"

    @pytest.mark.asyncio
    async def test_returns_none_when_not_found(self, storage, mock_pool):
        mock_pool.fetchrow = AsyncMock(return_value=None)

        result = await storage.get_scout("user-1", "nonexistent")
        assert result is None


class TestListScouts:
    @pytest.mark.asyncio
    async def test_returns_all_user_scouts(self, storage, mock_pool):
        scout_id_1 = uuid.uuid4()
        scout_id_2 = uuid.uuid4()

        # list_scouts does 3 fetch calls: scouts, runs, executions
        mock_pool.fetch = AsyncMock(side_effect=[
            # 1. Scout rows
            [
                {"id": scout_id_1, "name": "scout-1", "type": "beat",
                 "created_at": "2026-03-29T10:00:00"},
                {"id": scout_id_2, "name": "scout-2", "type": "web",
                 "created_at": "2026-03-29T11:00:00"},
            ],
            # 2. Run rows (empty = no runs yet)
            [],
            # 3. Execution rows (empty = no executions yet)
            [],
        ])

        result = await storage.list_scouts("user-1")
        assert len(result) == 2
        # Verify normalization adds DynamoDB-style names
        assert result[0]["scraper_name"] == "scout-1"
        assert result[0]["scout_type"] == "beat"
        assert result[0]["last_run"] is None
        assert result[0]["latest_execution"] is None


class TestListScoutsEnrichment:
    """Tests for list_scouts enrichment with last_run and latest_execution."""

    @pytest.mark.asyncio
    async def test_enriches_with_last_run(self, storage, mock_pool):
        """#40: list_scouts should include last_run data from scout_runs."""
        scout_id = uuid.uuid4()
        started = dt(2026, 4, 1, 20, 29, 52)

        mock_pool.fetch = AsyncMock(side_effect=[
            # Scouts
            [{"id": scout_id, "name": "scout-1", "type": "beat",
              "created_at": "2026-04-01T10:00:00"}],
            # Runs
            [{"scout_id": scout_id, "status": "success", "scraper_status": True,
              "criteria_status": False, "notification_sent": True,
              "articles_count": 5, "error_message": None,
              "started_at": started, "completed_at": started}],
            # Executions
            [],
        ])

        result = await storage.list_scouts("user-1")
        assert result[0]["last_run"] is not None
        assert result[0]["last_run"]["status"] == "success"
        assert result[0]["last_run"]["last_run"] == "04-01-2026 20:29"  # #45 format

    @pytest.mark.asyncio
    async def test_enriches_with_card_summary(self, storage, mock_pool):
        """#44: list_scouts should include card_summary from execution records."""
        scout_id = uuid.uuid4()
        completed = dt(2026, 4, 1, 20, 30, 0)

        mock_pool.fetch = AsyncMock(side_effect=[
            [{"id": scout_id, "name": "scout-1", "type": "web",
              "created_at": "2026-04-01T10:00:00"}],
            [],
            [{"scout_id": scout_id, "summary_text": "No changes detected",
              "is_duplicate": True, "completed_at": completed}],
        ])

        result = await storage.list_scouts("user-1")
        assert result[0]["card_summary"] == "No changes detected"

    @pytest.mark.asyncio
    async def test_normalizes_field_names(self, storage, mock_pool):
        """#34: Output should include both PG and DynamoDB field names."""
        scout_id = uuid.uuid4()
        mock_pool.fetch = AsyncMock(side_effect=[
            [{"id": scout_id, "name": "test", "type": "beat",
              "schedule_cron": "0 8 * * *", "schedule_timezone": "Europe/Zurich",
              "created_at": "2026-04-01T10:00:00"}],
            [], [],
        ])

        result = await storage.list_scouts("user-1")
        scout = result[0]
        # PostgreSQL names
        assert scout["name"] == "test"
        assert scout["type"] == "beat"
        assert scout["schedule_cron"] == "0 8 * * *"
        # DynamoDB aliases
        assert scout["scraper_name"] == "test"
        assert scout["scout_type"] == "beat"
        assert scout["cron_expression"] == "0 8 * * *"
        assert scout["timezone"] == "Europe/Zurich"


class TestDeleteScout:
    @pytest.mark.asyncio
    async def test_deletes_scout(self, storage, mock_pool):
        mock_pool.execute = AsyncMock(return_value="DELETE 1")

        await storage.delete_scout("user-1", "my-scout")
        mock_pool.execute.assert_called_once()


class TestUpdateScout:
    @pytest.mark.asyncio
    async def test_updates_and_returns_scout(self, storage, mock_pool):
        mock_pool.fetchrow = AsyncMock(return_value={
            "id": uuid.uuid4(),
            "name": "my-scout",
            "type": "beat",
            "criteria": "updated criteria",
        })

        result = await storage.update_scout("user-1", "my-scout", {"criteria": "updated criteria"})
        assert result["criteria"] == "updated criteria"


class TestDeactivateScout:
    @pytest.mark.asyncio
    async def test_deactivates_scout(self, storage, mock_pool):
        mock_pool.execute = AsyncMock(return_value="UPDATE 1")

        await storage.deactivate_scout(str(uuid.uuid4()))
        mock_pool.execute.assert_called_once()


class TestGetScoutById:
    @pytest.mark.asyncio
    async def test_returns_scout_by_id(self, storage, mock_pool):
        scout_id = str(uuid.uuid4())
        mock_pool.fetchrow = AsyncMock(return_value={
            "id": scout_id,
            "name": "my-scout",
            "type": "web",
        })

        result = await storage.get_scout_by_id(scout_id)
        assert result["name"] == "my-scout"
