"""Unit tests for DynamoDBUserStorage adapter."""
from __future__ import annotations

from decimal import Decimal
from unittest.mock import MagicMock, patch, call

import pytest
from botocore.exceptions import ClientError

from app.adapters.aws.user_storage import DynamoDBUserStorage


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_table():
    table = MagicMock()
    # Set up meta.client for transact_write_items (claim_seat)
    table.meta.client = MagicMock()
    table.meta.client.transact_write_items = MagicMock()
    return table


@pytest.fixture
def adapter(mock_table):
    with patch("app.adapters.aws.user_storage.get_table", return_value=mock_table):
        return DynamoDBUserStorage()


def _client_error(code: str) -> ClientError:
    """Build a botocore ClientError with the given error code."""
    return ClientError(
        {"Error": {"Code": code, "Message": "test"}},
        "TestOperation",
    )


# ---------------------------------------------------------------------------
# get_user
# ---------------------------------------------------------------------------

class TestGetUser:
    def test_returns_none_when_no_profile(self, adapter, mock_table):
        mock_table.get_item.return_value = {}
        result = adapter.get_user_sync("user1")
        assert result is None

    def test_merges_profile_and_credits(self, adapter, mock_table):
        profile = {
            "PK": "USER#user1", "SK": "PROFILE",
            "muckrock_id": "user1", "username": "alice",
            "tier": "pro", "timezone": "US/Eastern",
            "preferred_language": "en",
            "onboarding_completed": True,
            "default_location": {"city": "Boston"},
            "excluded_domains": ["example.com"],
            "cms_api_url": "https://cms.example.com",
            "cms_api_token": "secret",
            "org_id": "org123",
        }
        credits = {
            "PK": "USER#user1", "SK": "CREDITS",
            "balance": Decimal("42"),
        }

        def side_effect(**kwargs):
            if kwargs["Key"]["SK"] == "PROFILE":
                return {"Item": profile}
            return {"Item": credits}

        mock_table.get_item.side_effect = side_effect
        result = adapter.get_user_sync("user1")

        assert result is not None
        assert result["user_id"] == "user1"
        assert result["tier"] == "pro"
        assert result["credits"] == 42
        assert result["timezone"] == "US/Eastern"
        assert result["cms_api_url"] == "https://cms.example.com"
        assert result["has_cms_token"] is True
        assert result["org_id"] == "org123"

    def test_returns_defaults_when_fields_missing(self, adapter, mock_table):
        profile = {"PK": "USER#user1", "SK": "PROFILE"}
        credits = {"PK": "USER#user1", "SK": "CREDITS", "balance": Decimal("0")}

        def side_effect(**kwargs):
            if kwargs["Key"]["SK"] == "PROFILE":
                return {"Item": profile}
            return {"Item": credits}

        mock_table.get_item.side_effect = side_effect
        result = adapter.get_user_sync("user1")

        assert result["tier"] == "free"
        assert result["preferred_language"] == "en"
        assert result["onboarding_completed"] is False
        assert result["excluded_domains"] == []
        assert result["has_cms_token"] is False

    def test_credits_zero_when_no_credits_record(self, adapter, mock_table):
        profile = {"PK": "USER#user1", "SK": "PROFILE"}

        def side_effect(**kwargs):
            if kwargs["Key"]["SK"] == "PROFILE":
                return {"Item": profile}
            return {}

        mock_table.get_item.side_effect = side_effect
        result = adapter.get_user_sync("user1")
        assert result["credits"] == 0


# ---------------------------------------------------------------------------
# create_or_update_user
# ---------------------------------------------------------------------------

class TestCreateOrUpdateUser:
    def test_puts_profile_item(self, adapter, mock_table):
        adapter.create_or_update_user_sync("user1", {"tier": "pro", "username": "alice"})
        mock_table.put_item.assert_called_once()
        item = mock_table.put_item.call_args[1]["Item"]
        assert item["PK"] == "USER#user1"
        assert item["SK"] == "PROFILE"
        assert item["tier"] == "pro"

    def test_stores_all_data_fields(self, adapter, mock_table):
        data = {"tier": "free", "muckrock_id": "m1", "extra": "value"}
        adapter.create_or_update_user_sync("user1", data)
        item = mock_table.put_item.call_args[1]["Item"]
        assert item["extra"] == "value"

    def test_converts_float_coordinates_to_decimal(self, adapter, mock_table):
        """Regression: MapTiler coordinates are floats, DynamoDB rejects them."""
        data = {
            "tier": "free",
            "default_location": {
                "displayName": "Zurich, Switzerland",
                "city": "Zurich",
                "country": "CH",
                "locationType": "city",
                "maptilerId": "abc123",
                "coordinates": {"lat": 47.36667, "lon": 8.55},
            },
        }
        adapter.create_or_update_user_sync("user1", data)
        item = mock_table.put_item.call_args[1]["Item"]
        coords = item["default_location"]["coordinates"]
        assert isinstance(coords["lat"], Decimal)
        assert isinstance(coords["lon"], Decimal)


# ---------------------------------------------------------------------------
# update_profile
# ---------------------------------------------------------------------------

class TestUpdateProfile:
    def test_builds_set_expression_for_allowed_fields(self, adapter, mock_table):
        adapter.update_profile_sync("user1", {
            "timezone": "US/Pacific",
            "preferred_language": "fr",
        })
        mock_table.update_item.assert_called_once()
        kwargs = mock_table.update_item.call_args[1]
        assert kwargs["Key"] == {"PK": "USER#user1", "SK": "PROFILE"}
        assert "SET" in kwargs["UpdateExpression"]

    def test_ignores_disallowed_fields(self, adapter, mock_table):
        adapter.update_profile_sync("user1", {
            "timezone": "US/Pacific",
            "evil_field": "hacked",
        })
        kwargs = mock_table.update_item.call_args[1]
        values = kwargs["ExpressionAttributeValues"]
        # Only timezone should be present, not evil_field
        assert len(values) == 1

    def test_no_op_when_no_allowed_fields(self, adapter, mock_table):
        adapter.update_profile_sync("user1", {"evil_field": "hacked"})
        mock_table.update_item.assert_not_called()

    def test_all_allowed_fields_accepted(self, adapter, mock_table):
        updates = {
            "timezone": "UTC",
            "preferred_language": "de",
            "default_location": {"city": "Berlin"},
            "excluded_domains": ["spam.com"],
            "onboarding_completed": True,
            "onboarding_tour_completed": True,
            "cms_api_url": "https://cms.example.com",
            "cms_api_token": "secret",
        }
        adapter.update_profile_sync("user1", updates)
        kwargs = mock_table.update_item.call_args[1]
        values = kwargs["ExpressionAttributeValues"]
        assert len(values) == 8

    def test_converts_float_coordinates_to_decimal(self, adapter, mock_table):
        """Regression: MapTiler coordinates are floats, DynamoDB rejects them."""
        updates = {
            "default_location": {
                "displayName": "Oslo, Norway",
                "city": "Oslo",
                "country": "NO",
                "locationType": "city",
                "maptilerId": "xyz789",
                "coordinates": {"lat": 59.9139, "lon": 10.7522},
            },
        }
        adapter.update_profile_sync("user1", updates)
        kwargs = mock_table.update_item.call_args[1]
        location = kwargs["ExpressionAttributeValues"][":default_location"]
        coords = location["coordinates"]
        assert isinstance(coords["lat"], Decimal)
        assert isinstance(coords["lon"], Decimal)


# ---------------------------------------------------------------------------
# get_cms_config
# ---------------------------------------------------------------------------

class TestGetCmsConfig:
    def test_returns_cms_fields_from_profile(self, adapter, mock_table):
        mock_table.get_item.return_value = {
            "Item": {
                "PK": "USER#user1", "SK": "PROFILE",
                "cms_api_url": "https://cms.example.com",
                "cms_api_token": "secret",
            }
        }
        result = adapter.get_cms_config_sync("user1")
        assert result == {"cms_api_url": "https://cms.example.com", "cms_api_token": "secret"}

    def test_returns_nones_when_no_profile(self, adapter, mock_table):
        mock_table.get_item.return_value = {}
        result = adapter.get_cms_config_sync("user1")
        assert result == {"cms_api_url": None, "cms_api_token": None}

    def test_returns_nones_when_fields_missing(self, adapter, mock_table):
        mock_table.get_item.return_value = {
            "Item": {"PK": "USER#user1", "SK": "PROFILE"}
        }
        result = adapter.get_cms_config_sync("user1")
        assert result == {"cms_api_url": None, "cms_api_token": None}


# ---------------------------------------------------------------------------
# get_balance
# ---------------------------------------------------------------------------

class TestGetBalance:
    def test_returns_balance_as_int(self, adapter, mock_table):
        mock_table.get_item.return_value = {
            "Item": {"PK": "USER#user1", "SK": "CREDITS", "balance": Decimal("42")}
        }
        result = adapter.get_balance_sync("user1")
        assert result == 42
        assert isinstance(result, int)

    def test_returns_zero_when_no_credits(self, adapter, mock_table):
        mock_table.get_item.return_value = {}
        result = adapter.get_balance_sync("user1")
        assert result == 0

    def test_returns_zero_when_balance_missing(self, adapter, mock_table):
        mock_table.get_item.return_value = {
            "Item": {"PK": "USER#user1", "SK": "CREDITS"}
        }
        result = adapter.get_balance_sync("user1")
        assert result == 0


# ---------------------------------------------------------------------------
# create_credits
# ---------------------------------------------------------------------------

class TestCreateCredits:
    def test_puts_credits_item(self, adapter, mock_table):
        adapter.create_credits_sync("user1", monthly_cap=100, tier="free")
        mock_table.put_item.assert_called_once()
        item = mock_table.put_item.call_args[1]["Item"]
        assert item["PK"] == "USER#user1"
        assert item["SK"] == "CREDITS"
        assert item["balance"] == 100
        assert item["monthly_cap"] == 100
        assert item["tier"] == "free"

    def test_includes_last_reset_date(self, adapter, mock_table):
        adapter.create_credits_sync("user1", monthly_cap=100, tier="free")
        item = mock_table.put_item.call_args[1]["Item"]
        assert "last_reset_date" in item

    def test_includes_update_on(self, adapter, mock_table):
        adapter.create_credits_sync("user1", monthly_cap=1000, tier="pro",
                                    update_on="2025-01-01")
        item = mock_table.put_item.call_args[1]["Item"]
        assert item["update_on"] == "2025-01-01"

    def test_update_on_defaults_to_none(self, adapter, mock_table):
        adapter.create_credits_sync("user1", monthly_cap=100, tier="free")
        item = mock_table.put_item.call_args[1]["Item"]
        assert item["update_on"] is None


# ---------------------------------------------------------------------------
# update_credits
# ---------------------------------------------------------------------------

class TestUpdateCredits:
    def test_builds_dynamic_set_expression(self, adapter, mock_table):
        adapter.update_credits_sync("user1", {
            "monthly_cap": 1000,
            "tier": "pro",
        })
        mock_table.update_item.assert_called_once()
        kwargs = mock_table.update_item.call_args[1]
        assert kwargs["Key"] == {"PK": "USER#user1", "SK": "CREDITS"}
        assert "SET" in kwargs["UpdateExpression"]

    def test_no_op_when_empty_updates(self, adapter, mock_table):
        adapter.update_credits_sync("user1", {})
        mock_table.update_item.assert_not_called()


# ---------------------------------------------------------------------------
# decrement_credits
# ---------------------------------------------------------------------------

class TestDecrementCredits:
    def test_returns_true_on_success(self, adapter, mock_table):
        result = adapter.decrement_credits_sync("user1", 5)
        assert result is True
        mock_table.update_item.assert_called_once()

    def test_uses_condition_expression(self, adapter, mock_table):
        adapter.decrement_credits_sync("user1", 5)
        kwargs = mock_table.update_item.call_args[1]
        assert "balance >= :cost" in kwargs["ConditionExpression"]
        assert kwargs["ExpressionAttributeValues"][":cost"] == 5

    def test_returns_false_on_condition_failure(self, adapter, mock_table):
        mock_table.update_item.side_effect = _client_error("ConditionalCheckFailedException")
        result = adapter.decrement_credits_sync("user1", 5)
        assert result is False

    def test_reraises_non_condition_errors(self, adapter, mock_table):
        mock_table.update_item.side_effect = _client_error("InternalServerError")
        with pytest.raises(ClientError):
            adapter.decrement_credits_sync("user1", 5)


# ---------------------------------------------------------------------------
# create_org
# ---------------------------------------------------------------------------

class TestCreateOrg:
    def test_puts_org_credits_item(self, adapter, mock_table):
        adapter.create_org_sync("org1", monthly_cap=5000,
                                update_on="2025-06-01", org_name="Newsroom")
        mock_table.put_item.assert_called_once()
        item = mock_table.put_item.call_args[1]["Item"]
        assert item["PK"] == "ORG#org1"
        assert item["SK"] == "CREDITS"
        assert item["balance"] == 5000
        assert item["monthly_cap"] == 5000
        assert item["seated_count"] == 0
        assert item["tier"] == "team"
        assert item["org_name"] == "Newsroom"
        assert "created_at" in item

    def test_uses_condition_expression(self, adapter, mock_table):
        adapter.create_org_sync("org1", monthly_cap=5000,
                                update_on=None, org_name="Test")
        kwargs = mock_table.put_item.call_args[1]
        assert "attribute_not_exists(PK)" in kwargs.get("ConditionExpression", "")

    def test_silently_catches_existing_org(self, adapter, mock_table):
        mock_table.put_item.side_effect = _client_error("ConditionalCheckFailedException")
        # Should not raise
        adapter.create_org_sync("org1", monthly_cap=5000,
                                update_on=None, org_name="Test")

    def test_reraises_non_condition_errors(self, adapter, mock_table):
        mock_table.put_item.side_effect = _client_error("InternalServerError")
        with pytest.raises(ClientError):
            adapter.create_org_sync("org1", monthly_cap=5000,
                                    update_on=None, org_name="Test")


# ---------------------------------------------------------------------------
# get_org_credits
# ---------------------------------------------------------------------------

class TestGetOrgCredits:
    def test_returns_dict_with_all_fields(self, adapter, mock_table):
        mock_table.get_item.return_value = {
            "Item": {
                "PK": "ORG#org1", "SK": "CREDITS",
                "balance": Decimal("4500"),
                "monthly_cap": Decimal("5000"),
                "seated_count": Decimal("3"),
                "org_name": "Newsroom",
                "update_on": "2025-06-01",
            }
        }
        result = adapter.get_org_credits_sync("org1")
        assert result["balance"] == 4500
        assert result["monthly_cap"] == 5000
        assert result["seated_count"] == 3
        assert result["org_name"] == "Newsroom"
        assert result["update_on"] == "2025-06-01"

    def test_returns_none_when_not_found(self, adapter, mock_table):
        mock_table.get_item.return_value = {}
        result = adapter.get_org_credits_sync("org1")
        assert result is None

    def test_converts_decimals_to_int(self, adapter, mock_table):
        mock_table.get_item.return_value = {
            "Item": {
                "PK": "ORG#org1", "SK": "CREDITS",
                "balance": Decimal("100"),
                "monthly_cap": Decimal("200"),
                "seated_count": Decimal("1"),
            }
        }
        result = adapter.get_org_credits_sync("org1")
        assert isinstance(result["balance"], int)
        assert isinstance(result["monthly_cap"], int)
        assert isinstance(result["seated_count"], int)


# ---------------------------------------------------------------------------
# get_org_balance
# ---------------------------------------------------------------------------

class TestGetOrgBalance:
    def test_returns_balance_as_int(self, adapter, mock_table):
        mock_table.get_item.return_value = {
            "Item": {"PK": "ORG#org1", "SK": "CREDITS", "balance": Decimal("4500")}
        }
        result = adapter.get_org_balance_sync("org1")
        assert result == 4500
        assert isinstance(result, int)

    def test_returns_zero_when_not_found(self, adapter, mock_table):
        mock_table.get_item.return_value = {}
        result = adapter.get_org_balance_sync("org1")
        assert result == 0


# ---------------------------------------------------------------------------
# decrement_org_credits
# ---------------------------------------------------------------------------

class TestDecrementOrgCredits:
    def test_returns_true_on_success(self, adapter, mock_table):
        result = adapter.decrement_org_credits_sync("org1", 10)
        assert result is True

    def test_uses_org_key(self, adapter, mock_table):
        adapter.decrement_org_credits_sync("org1", 10)
        kwargs = mock_table.update_item.call_args[1]
        assert kwargs["Key"] == {"PK": "ORG#org1", "SK": "CREDITS"}

    def test_returns_false_on_condition_failure(self, adapter, mock_table):
        mock_table.update_item.side_effect = _client_error("ConditionalCheckFailedException")
        result = adapter.decrement_org_credits_sync("org1", 10)
        assert result is False


# ---------------------------------------------------------------------------
# update_org_credits
# ---------------------------------------------------------------------------

class TestUpdateOrgCredits:
    def test_upgrade_uses_atomic_delta(self, adapter, mock_table):
        """Upgrade path: single atomic expression adds delta to balance."""
        adapter.update_org_credits_sync("org1", new_cap=6000, new_update_on="2025-07-01")
        assert mock_table.update_item.call_count == 1
        kwargs = mock_table.update_item.call_args_list[0][1]
        assert kwargs["Key"] == {"PK": "ORG#org1", "SK": "CREDITS"}
        assert "balance + (:new_cap - monthly_cap)" in kwargs["UpdateExpression"]
        assert "monthly_cap <= :new_cap" in kwargs["ConditionExpression"]
        assert kwargs["ExpressionAttributeValues"][":new_cap"] == 6000
        assert kwargs["ExpressionAttributeValues"][":uon"] == "2025-07-01"

    def test_downgrade_caps_balance(self, adapter, mock_table):
        """Downgrade path: update cap, then clamp balance."""
        # First call (upgrade) fails because cap is being lowered
        mock_table.update_item.side_effect = [
            _client_error("ConditionalCheckFailedException"),
            None,  # downgrade cap update
            None,  # clamp balance
        ]
        adapter.update_org_credits_sync("org1", new_cap=200, new_update_on="2025-07-01")
        assert mock_table.update_item.call_count == 3
        # Second call: set monthly_cap
        second = mock_table.update_item.call_args_list[1][1]
        assert second["ExpressionAttributeValues"][":cap"] == 200
        # Third call: clamp balance
        third = mock_table.update_item.call_args_list[2][1]
        assert "balance > :cap" in third["ConditionExpression"]

    def test_no_change_is_idempotent(self, adapter, mock_table):
        """Same cap = delta 0, balance unchanged."""
        adapter.update_org_credits_sync("org1", new_cap=5000, new_update_on="2025-07-01")
        assert mock_table.update_item.call_count == 1

    def test_skips_when_org_not_found(self, adapter, mock_table):
        """Both upgrade and downgrade paths fail = org doesn't exist."""
        mock_table.update_item.side_effect = [
            _client_error("ConditionalCheckFailedException"),  # upgrade path
            _client_error("ConditionalCheckFailedException"),  # downgrade path
        ]
        # Should not raise
        adapter.update_org_credits_sync("org1", new_cap=200, new_update_on="2025-07-01")

    def test_uses_condition_expression(self, adapter, mock_table):
        adapter.update_org_credits_sync("org1", new_cap=200, new_update_on="2025-07-01")
        kwargs = mock_table.update_item.call_args_list[0][1]
        assert "attribute_exists(PK)" in kwargs.get("ConditionExpression", "")


# ---------------------------------------------------------------------------
# claim_seat
# ---------------------------------------------------------------------------

class TestClaimSeat:
    def test_returns_true_on_success(self, adapter, mock_table):
        result = adapter.claim_seat_sync("org1", "user1", "free")
        assert result is True

    def test_uses_transact_write_items(self, adapter, mock_table):
        adapter.claim_seat_sync("org1", "user1", "free")
        mock_table.meta.client.transact_write_items.assert_called_once()

    def test_transaction_has_two_items(self, adapter, mock_table):
        adapter.claim_seat_sync("org1", "user1", "free")
        kwargs = mock_table.meta.client.transact_write_items.call_args[1]
        assert len(kwargs["TransactItems"]) == 2

    def test_first_item_updates_org_seated_count(self, adapter, mock_table):
        adapter.claim_seat_sync("org1", "user1", "free")
        kwargs = mock_table.meta.client.transact_write_items.call_args[1]
        update = kwargs["TransactItems"][0]["Update"]
        assert update["Key"]["PK"]["S"] == "ORG#org1"
        assert update["Key"]["SK"]["S"] == "CREDITS"
        assert "seated_count" in update["UpdateExpression"]
        assert "attribute_exists(PK)" in update["ConditionExpression"]

    def test_second_item_puts_member_record(self, adapter, mock_table):
        adapter.claim_seat_sync("org1", "user1", "free")
        kwargs = mock_table.meta.client.transact_write_items.call_args[1]
        put = kwargs["TransactItems"][1]["Put"]
        assert put["Item"]["PK"]["S"] == "ORG#org1"
        assert put["Item"]["SK"]["S"] == "MEMBER#user1"
        assert put["Item"]["tier_before_team"]["S"] == "free"
        assert "joined_at" in put["Item"]
        assert "attribute_not_exists(PK)" in put["ConditionExpression"]

    def test_returns_true_when_already_member(self, adapter, mock_table):
        """reason[1] = ConditionalCheckFailed means MEMBER# exists (re-login)."""
        error = _client_error("TransactionCanceledException")
        error.response["CancellationReasons"] = [
            {"Code": "None"},
            {"Code": "ConditionalCheckFailed"},
        ]
        mock_table.meta.client.transact_write_items.side_effect = error
        result = adapter.claim_seat_sync("org1", "user1", "free")
        assert result is True

    def test_returns_false_when_org_not_found(self, adapter, mock_table):
        """reason[0] = ConditionalCheckFailed means ORG# doesn't exist."""
        error = _client_error("TransactionCanceledException")
        error.response["CancellationReasons"] = [
            {"Code": "ConditionalCheckFailed"},
            {"Code": "None"},
        ]
        mock_table.meta.client.transact_write_items.side_effect = error
        result = adapter.claim_seat_sync("org1", "user1", "free")
        assert result is False

    def test_reraises_other_errors(self, adapter, mock_table):
        mock_table.meta.client.transact_write_items.side_effect = _client_error(
            "InternalServerError"
        )
        with pytest.raises(ClientError):
            adapter.claim_seat_sync("org1", "user1", "free")

    def test_stores_table_name(self, adapter, mock_table):
        """Both transactional items must specify the table name."""
        mock_table.name = "scraping-jobs"
        adapter.claim_seat_sync("org1", "user1", "free")
        kwargs = mock_table.meta.client.transact_write_items.call_args[1]
        update = kwargs["TransactItems"][0]["Update"]
        put = kwargs["TransactItems"][1]["Put"]
        assert update["TableName"] == "scraping-jobs"
        assert put["TableName"] == "scraping-jobs"


# ---------------------------------------------------------------------------
# cancel_team_org
# ---------------------------------------------------------------------------

class TestCancelTeamOrg:
    def test_queries_member_records(self, adapter, mock_table):
        mock_table.query.return_value = {"Items": []}
        adapter.cancel_team_org_sync("org1")
        mock_table.query.assert_called_once()

    def test_reverts_member_to_pre_team_tier(self, adapter, mock_table):
        members = [
            {
                "PK": "ORG#org1",
                "SK": "MEMBER#user1",
                "tier_before_team": "pro",
            }
        ]
        mock_table.query.return_value = {"Items": members}

        # get_item for balance check
        mock_table.get_item.return_value = {
            "Item": {"balance": Decimal("500")}
        }

        adapter.cancel_team_org_sync("org1")

        # Should update USER#user1/PROFILE with tier=pro REMOVE org_id
        update_calls = mock_table.update_item.call_args_list
        profile_call = update_calls[0][1]
        assert profile_call["Key"] == {"PK": "USER#user1", "SK": "PROFILE"}
        assert ":tier" in profile_call["ExpressionAttributeValues"]
        assert profile_call["ExpressionAttributeValues"][":tier"] == "pro"

    def test_updates_credits_with_revert_cap(self, adapter, mock_table):
        members = [
            {
                "PK": "ORG#org1",
                "SK": "MEMBER#user1",
                "tier_before_team": "free",
            }
        ]
        mock_table.query.return_value = {"Items": members}
        mock_table.get_item.return_value = {
            "Item": {"balance": Decimal("50")}
        }

        adapter.cancel_team_org_sync("org1")

        update_calls = mock_table.update_item.call_args_list
        credits_call = update_calls[1][1]
        assert credits_call["Key"] == {"PK": "USER#user1", "SK": "CREDITS"}
        assert credits_call["ExpressionAttributeValues"][":cap"] == 100  # DEFAULT_FREE_CREDITS

    def test_caps_balance_on_downgrade(self, adapter, mock_table):
        members = [
            {
                "PK": "ORG#org1",
                "SK": "MEMBER#user1",
                "tier_before_team": "free",
            }
        ]
        mock_table.query.return_value = {"Items": members}
        # Balance (200) > free cap (100)
        mock_table.get_item.return_value = {
            "Item": {"balance": Decimal("200")}
        }

        adapter.cancel_team_org_sync("org1")

        # 3 update_item calls: profile, credits, balance cap
        assert mock_table.update_item.call_count == 3
        cap_call = mock_table.update_item.call_args_list[2][1]
        assert cap_call["ExpressionAttributeValues"][":cap"] == 100

    def test_no_balance_cap_when_below_limit(self, adapter, mock_table):
        members = [
            {
                "PK": "ORG#org1",
                "SK": "MEMBER#user1",
                "tier_before_team": "free",
            }
        ]
        mock_table.query.return_value = {"Items": members}
        # Balance (50) <= free cap (100) — no cap needed
        mock_table.get_item.return_value = {
            "Item": {"balance": Decimal("50")}
        }

        adapter.cancel_team_org_sync("org1")

        # Only 2 update_item calls: profile, credits (no balance cap)
        assert mock_table.update_item.call_count == 2

    def test_deletes_member_records(self, adapter, mock_table):
        members = [
            {"PK": "ORG#org1", "SK": "MEMBER#user1", "tier_before_team": "free"},
            {"PK": "ORG#org1", "SK": "MEMBER#user2", "tier_before_team": "pro"},
        ]
        mock_table.query.return_value = {"Items": members}
        mock_table.get_item.return_value = {"Item": {"balance": Decimal("50")}}

        adapter.cancel_team_org_sync("org1")

        # Check delete_item calls — member records + org credits
        delete_calls = [c for c in mock_table.delete_item.call_args_list]
        delete_keys = [c[1]["Key"] for c in delete_calls]

        assert {"PK": "ORG#org1", "SK": "MEMBER#user1"} in delete_keys
        assert {"PK": "ORG#org1", "SK": "MEMBER#user2"} in delete_keys

    def test_deletes_org_credits_record(self, adapter, mock_table):
        mock_table.query.return_value = {"Items": []}

        adapter.cancel_team_org_sync("org1")

        mock_table.delete_item.assert_called_once_with(
            Key={"PK": "ORG#org1", "SK": "CREDITS"}
        )

    def test_pro_tier_gets_pro_credits_cap(self, adapter, mock_table):
        members = [
            {
                "PK": "ORG#org1",
                "SK": "MEMBER#user1",
                "tier_before_team": "pro",
            }
        ]
        mock_table.query.return_value = {"Items": members}
        mock_table.get_item.return_value = {"Item": {"balance": Decimal("50")}}

        adapter.cancel_team_org_sync("org1")

        credits_call = mock_table.update_item.call_args_list[1][1]
        assert credits_call["ExpressionAttributeValues"][":cap"] == 1000  # DEFAULT_PRO_CREDITS

    def test_defaults_to_free_for_unknown_tier(self, adapter, mock_table):
        members = [
            {
                "PK": "ORG#org1",
                "SK": "MEMBER#user1",
                "tier_before_team": "unknown",
            }
        ]
        mock_table.query.return_value = {"Items": members}
        mock_table.get_item.return_value = {"Item": {"balance": Decimal("50")}}

        adapter.cancel_team_org_sync("org1")

        credits_call = mock_table.update_item.call_args_list[1][1]
        assert credits_call["ExpressionAttributeValues"][":cap"] == 100  # DEFAULT_FREE_CREDITS


# ---------------------------------------------------------------------------
# Async wrappers - smoke tests
# ---------------------------------------------------------------------------

class TestAsyncWrappers:
    @pytest.mark.asyncio
    async def test_get_user_async(self, adapter, mock_table):
        mock_table.get_item.return_value = {}
        result = await adapter.get_user("user1")
        assert result is None

    @pytest.mark.asyncio
    async def test_create_or_update_user_async(self, adapter, mock_table):
        result = await adapter.create_or_update_user("user1", {"tier": "free"})
        mock_table.put_item.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_profile_async(self, adapter, mock_table):
        await adapter.update_profile("user1", {"timezone": "UTC"})
        mock_table.update_item.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_cms_config_async(self, adapter, mock_table):
        mock_table.get_item.return_value = {}
        result = await adapter.get_cms_config("user1")
        assert result == {"cms_api_url": None, "cms_api_token": None}

    @pytest.mark.asyncio
    async def test_get_balance_async(self, adapter, mock_table):
        mock_table.get_item.return_value = {}
        result = await adapter.get_balance("user1")
        assert result == 0

    @pytest.mark.asyncio
    async def test_create_credits_async(self, adapter, mock_table):
        await adapter.create_credits("user1", monthly_cap=100, tier="free")
        mock_table.put_item.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_credits_async(self, adapter, mock_table):
        await adapter.update_credits("user1", {"tier": "pro"})
        mock_table.update_item.assert_called_once()

    @pytest.mark.asyncio
    async def test_decrement_credits_async(self, adapter, mock_table):
        result = await adapter.decrement_credits("user1", 5)
        assert result is True

    @pytest.mark.asyncio
    async def test_create_org_async(self, adapter, mock_table):
        await adapter.create_org("org1", 5000, None, "Test")
        mock_table.put_item.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_org_credits_async(self, adapter, mock_table):
        mock_table.get_item.return_value = {}
        result = await adapter.get_org_credits("org1")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_org_balance_async(self, adapter, mock_table):
        mock_table.get_item.return_value = {}
        result = await adapter.get_org_balance("org1")
        assert result == 0

    @pytest.mark.asyncio
    async def test_decrement_org_credits_async(self, adapter, mock_table):
        result = await adapter.decrement_org_credits("org1", 10)
        assert result is True

    @pytest.mark.asyncio
    async def test_update_org_credits_async(self, adapter, mock_table):
        await adapter.update_org_credits("org1", 200, "2025-07-01")
        mock_table.update_item.assert_called()

    @pytest.mark.asyncio
    async def test_claim_seat_async(self, adapter, mock_table):
        result = await adapter.claim_seat("org1", "user1", "free")
        assert result is True

    @pytest.mark.asyncio
    async def test_cancel_team_org_async(self, adapter, mock_table):
        mock_table.query.return_value = {"Items": []}
        await adapter.cancel_team_org("org1")
        mock_table.delete_item.assert_called_once()
