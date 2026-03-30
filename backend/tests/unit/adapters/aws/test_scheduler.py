"""Unit tests for EventBridgeScheduler adapter."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from botocore.exceptions import ClientError

from app.adapters.aws.scheduler import EventBridgeScheduler


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _client_error(code: str) -> ClientError:
    """Build a botocore ClientError with the given error code."""
    return ClientError(
        {"Error": {"Code": code, "Message": "test"}},
        "TestOperation",
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_boto3_client():
    """Patch boto3.client at the scheduler module level."""
    with patch("app.adapters.aws.scheduler.boto3") as mock_boto3:
        mock_client = MagicMock()
        mock_boto3.client.return_value = mock_client
        yield mock_boto3, mock_client


@pytest.fixture
def adapter(mock_boto3_client):
    """EventBridgeScheduler with mocked boto3."""
    _, mock_client = mock_boto3_client
    with patch("app.adapters.aws.scheduler.get_settings") as mock_settings:
        settings = MagicMock()
        settings.aws_region = "eu-central-1"
        settings.scraper_lambda_arn = "arn:aws:lambda:eu-central-1:123:function:scraper"
        settings.eventbridge_role_arn = "arn:aws:iam::123:role/eventbridge-role"
        mock_settings.return_value = settings
        inst = EventBridgeScheduler()
    # Attach the mock client so tests can introspect it
    inst.scheduler = mock_client
    return inst


# ---------------------------------------------------------------------------
# __init__
# ---------------------------------------------------------------------------

class TestInit:
    def test_creates_scheduler_client(self, mock_boto3_client):
        mock_boto3, _ = mock_boto3_client
        with patch("app.adapters.aws.scheduler.get_settings") as mock_settings:
            settings = MagicMock()
            settings.aws_region = "us-east-1"
            settings.scraper_lambda_arn = "arn:lambda"
            settings.eventbridge_role_arn = "arn:role"
            mock_settings.return_value = settings
            EventBridgeScheduler()
        mock_boto3.client.assert_called_once_with("scheduler", region_name="us-east-1")

    def test_stores_lambda_arn_from_settings(self, mock_boto3_client):
        mock_boto3, _ = mock_boto3_client
        with patch("app.adapters.aws.scheduler.get_settings") as mock_settings:
            settings = MagicMock()
            settings.aws_region = "eu-central-1"
            settings.scraper_lambda_arn = "arn:aws:lambda::func"
            settings.eventbridge_role_arn = "arn:aws:iam::role"
            mock_settings.return_value = settings
            inst = EventBridgeScheduler()
        assert inst.scraper_lambda_arn == "arn:aws:lambda::func"

    def test_stores_role_arn_from_settings(self, mock_boto3_client):
        mock_boto3, _ = mock_boto3_client
        with patch("app.adapters.aws.scheduler.get_settings") as mock_settings:
            settings = MagicMock()
            settings.aws_region = "eu-central-1"
            settings.scraper_lambda_arn = "arn:lambda"
            settings.eventbridge_role_arn = "arn:aws:iam::role"
            mock_settings.return_value = settings
            inst = EventBridgeScheduler()
        assert inst.eventbridge_role_arn == "arn:aws:iam::role"


# ---------------------------------------------------------------------------
# create_schedule_sync
# ---------------------------------------------------------------------------

class TestCreateScheduleSync:
    def test_calls_create_schedule_with_correct_args(self, adapter):
        adapter.scheduler.create_schedule.return_value = {
            "ScheduleArn": "arn:aws:scheduler:eu-central-1:123:schedule/test"
        }
        adapter.create_schedule_sync(
            schedule_name="my-schedule",
            cron="cron(0 8 * * ? *)",
            target_config={
                "lambda_arn": "arn:lambda:func",
                "role_arn": "arn:iam:role",
                "input": '{"key": "value"}',
            },
        )
        adapter.scheduler.create_schedule.assert_called_once_with(
            Name="my-schedule",
            ScheduleExpression="cron(0 8 * * ? *)",
            State="ENABLED",
            Target={
                "Arn": "arn:lambda:func",
                "RoleArn": "arn:iam:role",
                "Input": '{"key": "value"}',
            },
            FlexibleTimeWindow={"Mode": "OFF"},
        )

    def test_returns_schedule_arn(self, adapter):
        expected_arn = "arn:aws:scheduler:eu-central-1:123:schedule/my-schedule"
        adapter.scheduler.create_schedule.return_value = {
            "ScheduleArn": expected_arn
        }
        result = adapter.create_schedule_sync(
            "my-schedule",
            "cron(0 8 * * ? *)",
            {"lambda_arn": "arn:l", "role_arn": "arn:r", "input": "{}"},
        )
        assert result == expected_arn

    def test_uses_default_lambda_arn_when_not_in_target_config(self, adapter):
        adapter.scheduler.create_schedule.return_value = {"ScheduleArn": "arn:sched"}
        adapter.create_schedule_sync(
            "my-schedule",
            "cron(0 8 * * ? *)",
            {"role_arn": "arn:r", "input": "{}"},
        )
        call_kwargs = adapter.scheduler.create_schedule.call_args[1]
        assert call_kwargs["Target"]["Arn"] == adapter.scraper_lambda_arn

    def test_uses_default_role_arn_when_not_in_target_config(self, adapter):
        adapter.scheduler.create_schedule.return_value = {"ScheduleArn": "arn:sched"}
        adapter.create_schedule_sync(
            "my-schedule",
            "cron(0 8 * * ? *)",
            {"lambda_arn": "arn:l", "input": "{}"},
        )
        call_kwargs = adapter.scheduler.create_schedule.call_args[1]
        assert call_kwargs["Target"]["RoleArn"] == adapter.eventbridge_role_arn

    def test_uses_empty_json_input_when_not_in_target_config(self, adapter):
        adapter.scheduler.create_schedule.return_value = {"ScheduleArn": "arn:sched"}
        adapter.create_schedule_sync(
            "my-schedule",
            "cron(0 8 * * ? *)",
            {"lambda_arn": "arn:l", "role_arn": "arn:r"},
        )
        call_kwargs = adapter.scheduler.create_schedule.call_args[1]
        assert call_kwargs["Target"]["Input"] == "{}"

    def test_returns_empty_string_when_no_arn_in_response(self, adapter):
        adapter.scheduler.create_schedule.return_value = {}
        result = adapter.create_schedule_sync(
            "my-schedule",
            "cron(0 8 * * ? *)",
            {"lambda_arn": "arn:l", "role_arn": "arn:r", "input": "{}"},
        )
        assert result == ""

    def test_schedule_expression_passed_verbatim(self, adapter):
        adapter.scheduler.create_schedule.return_value = {"ScheduleArn": "arn:sched"}
        cron_expr = "cron(30 9 ? * MON-FRI *)"
        adapter.create_schedule_sync(
            "my-schedule", cron_expr, {"lambda_arn": "arn:l", "role_arn": "arn:r"}
        )
        call_kwargs = adapter.scheduler.create_schedule.call_args[1]
        assert call_kwargs["ScheduleExpression"] == cron_expr

    def test_flexible_time_window_is_off(self, adapter):
        adapter.scheduler.create_schedule.return_value = {"ScheduleArn": "arn:sched"}
        adapter.create_schedule_sync(
            "my-schedule",
            "cron(0 8 * * ? *)",
            {"lambda_arn": "arn:l", "role_arn": "arn:r"},
        )
        call_kwargs = adapter.scheduler.create_schedule.call_args[1]
        assert call_kwargs["FlexibleTimeWindow"] == {"Mode": "OFF"}

    def test_state_is_enabled(self, adapter):
        adapter.scheduler.create_schedule.return_value = {"ScheduleArn": "arn:sched"}
        adapter.create_schedule_sync(
            "my-schedule",
            "cron(0 8 * * ? *)",
            {"lambda_arn": "arn:l", "role_arn": "arn:r"},
        )
        call_kwargs = adapter.scheduler.create_schedule.call_args[1]
        assert call_kwargs["State"] == "ENABLED"

    def test_propagates_client_errors(self, adapter):
        adapter.scheduler.create_schedule.side_effect = _client_error(
            "ValidationException"
        )
        with pytest.raises(ClientError):
            adapter.create_schedule_sync(
                "bad-schedule",
                "cron(0 8 * * ? *)",
                {"lambda_arn": "arn:l", "role_arn": "arn:r"},
            )


# ---------------------------------------------------------------------------
# delete_schedule_sync
# ---------------------------------------------------------------------------

class TestDeleteScheduleSync:
    def test_calls_delete_schedule_with_name(self, adapter):
        adapter.delete_schedule_sync("my-schedule")
        adapter.scheduler.delete_schedule.assert_called_once_with(Name="my-schedule")

    def test_suppresses_resource_not_found(self, adapter):
        adapter.scheduler.delete_schedule.side_effect = _client_error(
            "ResourceNotFoundException"
        )
        # Should not raise
        adapter.delete_schedule_sync("missing-schedule")

    def test_reraises_other_client_errors(self, adapter):
        adapter.scheduler.delete_schedule.side_effect = _client_error(
            "InternalServerError"
        )
        with pytest.raises(ClientError):
            adapter.delete_schedule_sync("my-schedule")

    def test_returns_none_on_success(self, adapter):
        result = adapter.delete_schedule_sync("my-schedule")
        assert result is None

    def test_returns_none_when_not_found(self, adapter):
        adapter.scheduler.delete_schedule.side_effect = _client_error(
            "ResourceNotFoundException"
        )
        result = adapter.delete_schedule_sync("missing-schedule")
        assert result is None


# ---------------------------------------------------------------------------
# update_schedule
# ---------------------------------------------------------------------------

class TestUpdateSchedule:
    @pytest.mark.asyncio
    async def test_raises_not_implemented(self, adapter):
        with pytest.raises(NotImplementedError):
            await adapter.update_schedule("my-schedule", cron="cron(0 8 * * ? *)")

    @pytest.mark.asyncio
    async def test_raises_with_no_args(self, adapter):
        with pytest.raises(NotImplementedError):
            await adapter.update_schedule("my-schedule")


# ---------------------------------------------------------------------------
# Async wrappers
# ---------------------------------------------------------------------------

class TestAsyncWrappers:
    @pytest.mark.asyncio
    async def test_create_schedule_async(self, adapter):
        adapter.scheduler.create_schedule.return_value = {
            "ScheduleArn": "arn:aws:scheduler:eu-central-1:123:schedule/test"
        }
        result = await adapter.create_schedule(
            "my-schedule",
            "cron(0 8 * * ? *)",
            {"lambda_arn": "arn:l", "role_arn": "arn:r", "input": "{}"},
        )
        assert result == "arn:aws:scheduler:eu-central-1:123:schedule/test"
        adapter.scheduler.create_schedule.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_schedule_async(self, adapter):
        await adapter.delete_schedule("my-schedule")
        adapter.scheduler.delete_schedule.assert_called_once_with(Name="my-schedule")

    @pytest.mark.asyncio
    async def test_delete_schedule_async_suppresses_not_found(self, adapter):
        adapter.scheduler.delete_schedule.side_effect = _client_error(
            "ResourceNotFoundException"
        )
        # Should not raise
        await adapter.delete_schedule("missing-schedule")
