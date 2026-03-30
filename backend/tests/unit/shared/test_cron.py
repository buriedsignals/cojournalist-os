"""
Unit tests for the cron expression builder.

These tests verify that:
1. Daily, weekly, and monthly cron expressions are generated correctly
2. Time parsing handles all edge cases
3. Day of week conversion matches AWS EventBridge expectations
"""
import pytest
from app.services.cron import build_scraper_cron, parse_time_string, CronBuilderError


class TestTimeParser:
    """Tests for the parse_time_string function."""

    def test_parse_8am(self):
        """08:00 should parse to hour=8, minute=0."""
        assert parse_time_string("08:00") == (8, 0)

    def test_parse_8pm_24h(self):
        """20:00 should parse to hour=20, minute=0."""
        assert parse_time_string("20:00") == (20, 0)

    def test_parse_noon(self):
        """12:00 should parse to hour=12, minute=0."""
        assert parse_time_string("12:00") == (12, 0)

    def test_parse_midnight(self):
        """00:00 should parse to hour=0, minute=0."""
        assert parse_time_string("00:00") == (0, 0)

    def test_parse_with_minutes(self):
        """14:30 should parse to hour=14, minute=30."""
        assert parse_time_string("14:30") == (14, 30)

    def test_parse_invalid_format(self):
        """Invalid format should raise CronBuilderError."""
        with pytest.raises(CronBuilderError, match="HH:MM format"):
            parse_time_string("8pm")

    def test_parse_invalid_hour(self):
        """Hour > 23 should raise CronBuilderError."""
        with pytest.raises(CronBuilderError, match="between 00:00 and 23:59"):
            parse_time_string("24:00")

    def test_parse_invalid_minute(self):
        """Minute > 59 should raise CronBuilderError."""
        with pytest.raises(CronBuilderError, match="between 00:00 and 23:59"):
            parse_time_string("12:60")


class TestDailyCron:
    """Tests for daily cron expression generation."""

    def test_daily_8pm_zurich(self):
        """Daily at 8PM Zurich should generate '0 20 * * ? *'."""
        result = build_scraper_cron("Europe/Zurich", "daily", 1, "20:00")
        assert result.expression == "0 20 * * ? *"
        assert result.timezone == "Europe/Zurich"
        assert result.hour == 20
        assert result.minute == 0
        assert result.day_of_week is None
        assert result.day_of_month is None

    def test_daily_noon(self):
        """Daily at noon should generate '0 12 * * ? *'."""
        result = build_scraper_cron("Europe/Zurich", "daily", 1, "12:00")
        assert result.expression == "0 12 * * ? *"

    def test_daily_with_minutes(self):
        """Daily at 14:30 should generate '30 14 * * ? *'."""
        result = build_scraper_cron("Europe/Zurich", "daily", 1, "14:30")
        assert result.expression == "30 14 * * ? *"

    def test_daily_ignores_day_number(self):
        """Daily cron should ignore day_number parameter."""
        result1 = build_scraper_cron("Europe/Zurich", "daily", 1, "20:00")
        result2 = build_scraper_cron("Europe/Zurich", "daily", 5, "20:00")
        assert result1.expression == result2.expression


class TestWeeklyCron:
    """Tests for weekly cron expression generation."""

    def test_weekly_monday_12pm(self):
        """Weekly Monday at 12PM should generate '0 12 ? * 2 *'.

        Note: AWS EventBridge uses 1=Sunday, 2=Monday, etc.
        Frontend uses 1=Monday, 2=Tuesday, etc.
        So frontend day 1 (Monday) becomes EventBridge day 2.
        """
        result = build_scraper_cron("Europe/Zurich", "weekly", 1, "12:00")
        assert result.expression == "0 12 ? * 2 *"
        assert result.day_of_week == 2  # EventBridge Monday

    def test_weekly_tuesday(self):
        """Weekly Tuesday (day 2) should generate day_of_week=3."""
        result = build_scraper_cron("Europe/Zurich", "weekly", 2, "12:00")
        assert result.expression == "0 12 ? * 3 *"
        assert result.day_of_week == 3

    def test_weekly_sunday(self):
        """Weekly Sunday (day 7) should generate day_of_week=1."""
        result = build_scraper_cron("Europe/Zurich", "weekly", 7, "12:00")
        assert result.expression == "0 12 ? * 1 *"
        assert result.day_of_week == 1

    def test_weekly_invalid_day(self):
        """Day outside 1-7 should raise CronBuilderError."""
        with pytest.raises(CronBuilderError, match="between 1"):
            build_scraper_cron("Europe/Zurich", "weekly", 0, "12:00")
        with pytest.raises(CronBuilderError, match="between 1"):
            build_scraper_cron("Europe/Zurich", "weekly", 8, "12:00")


class TestMonthlyCron:
    """Tests for monthly cron expression generation."""

    def test_monthly_15th(self):
        """Monthly on 15th should generate '0 12 15 * ? *'."""
        result = build_scraper_cron("Europe/Zurich", "monthly", 15, "12:00")
        assert result.expression == "0 12 15 * ? *"
        assert result.day_of_month == 15

    def test_monthly_1st(self):
        """Monthly on 1st should generate '0 12 1 * ? *'."""
        result = build_scraper_cron("Europe/Zurich", "monthly", 1, "12:00")
        assert result.expression == "0 12 1 * ? *"
        assert result.day_of_month == 1

    def test_monthly_31st(self):
        """Monthly on 31st should generate '0 12 31 * ? *'."""
        result = build_scraper_cron("Europe/Zurich", "monthly", 31, "12:00")
        assert result.expression == "0 12 31 * ? *"
        assert result.day_of_month == 31

    def test_monthly_invalid_day(self):
        """Day outside 1-31 should raise CronBuilderError."""
        with pytest.raises(CronBuilderError, match="between 1"):
            build_scraper_cron("Europe/Zurich", "monthly", 0, "12:00")
        with pytest.raises(CronBuilderError, match="between 1"):
            build_scraper_cron("Europe/Zurich", "monthly", 32, "12:00")


class TestTimezoneHandling:
    """Tests for timezone parameter handling."""

    def test_timezone_preserved(self):
        """Timezone should be preserved in result."""
        result = build_scraper_cron("America/New_York", "daily", 1, "20:00")
        assert result.timezone == "America/New_York"

    def test_default_timezone_when_none(self):
        """None timezone should use default from settings."""
        result = build_scraper_cron(None, "daily", 1, "20:00")
        # Should not raise and should have a timezone set
        assert result.timezone is not None


class TestCronMetadata:
    """Tests for CronSchedule metadata generation."""

    def test_metadata_daily(self):
        """Daily schedule metadata should include hour/minute but no days."""
        result = build_scraper_cron("Europe/Zurich", "daily", 1, "20:00")
        metadata = result.metadata()
        assert metadata["hour"] == 20
        assert metadata["minute"] == 0
        assert metadata["day_of_week"] is None
        assert metadata["day_of_month"] is None
        assert metadata["timezone"] == "Europe/Zurich"

    def test_metadata_weekly(self):
        """Weekly schedule metadata should include day_of_week."""
        result = build_scraper_cron("Europe/Zurich", "weekly", 1, "20:00")
        metadata = result.metadata()
        assert metadata["day_of_week"] == 2  # EventBridge Monday
        assert metadata["day_of_month"] is None

    def test_metadata_monthly(self):
        """Monthly schedule metadata should include day_of_month."""
        result = build_scraper_cron("Europe/Zurich", "monthly", 15, "20:00")
        metadata = result.metadata()
        assert metadata["day_of_week"] is None
        assert metadata["day_of_month"] == 15


class TestInvalidRegularity:
    """Tests for invalid regularity values."""

    def test_invalid_regularity(self):
        """Unknown regularity should raise CronBuilderError."""
        with pytest.raises(CronBuilderError, match="Unsupported regularity"):
            build_scraper_cron("Europe/Zurich", "hourly", 1, "20:00")
