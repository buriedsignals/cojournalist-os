"""
Shared pytest fixtures and configuration for backend tests.

Environment variables:
- TEST_USER_ID: MuckRock user UUID for integration tests (required for real DynamoDB)
- TEST_EMAIL: Email address for notification tests (skip if not set)
- RESEND_API_KEY: Required for email sending tests
- OPENROUTER_API_KEY: Required for AI extraction tests
"""
import os
import pytest
from pathlib import Path
from dotenv import load_dotenv

# Load .env from project root (relative path - works from any machine)
env_path = Path(__file__).parent.parent.parent / ".env"
if env_path.exists():
    load_dotenv(env_path)

# Test configuration - use env vars or safe defaults
# IMPORTANT: Never hardcode real user IDs or credentials in tests
TEST_USER_ID = os.getenv("TEST_USER_ID", "test_user_integration")
TEST_EMAIL = os.getenv("TEST_EMAIL")  # Must be set explicitly for email tests
TEST_SCOUT_NAME = "TEST_Data_Scout"   # Generic name for tests


@pytest.fixture
def mock_user():
    """Standard mock user for tests that don't require real DynamoDB."""
    return {
        "user_id": "test_user",
        "email": "test@example.com",
        "credits": 100,
        "timezone": "UTC",
        "onboarding_completed": True,
        "needs_initialization": False,
        "preferred_language": "en",
        "tier": "free",
        "excluded_domains": [],
    }


@pytest.fixture
def integration_user_id():
    """
    User ID for integration tests requiring real DynamoDB.

    Skip test if TEST_USER_ID env var is not set to a real user.
    """
    user_id = os.getenv("TEST_USER_ID")
    if not user_id or user_id == "test_user_integration":
        pytest.skip("TEST_USER_ID not set - required for integration tests")
    return user_id


@pytest.fixture
def test_email():
    """
    Email address for notification tests.

    Skip test if TEST_EMAIL env var is not set.
    """
    email = os.getenv("TEST_EMAIL")
    if not email:
        pytest.skip("TEST_EMAIL not set - required for email tests")
    return email
