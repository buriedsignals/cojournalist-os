"""
Application configuration using environment variables.

PURPOSE: Single Settings class loaded from environment variables via
pydantic_settings. Provides API keys, AWS config, feature flags, and
credit amounts used throughout the application.

DEPENDS ON: (pydantic_settings only — no app imports)
USED BY: Nearly all services and routers (imported as `settings` or `get_settings()`)
"""
import os
from pathlib import Path
from typing import Optional
from pydantic_settings import BaseSettings


BASE_DIR = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # App settings
    app_name: str = "coJournalist API"
    debug: bool = False
    environment: str = os.getenv("ENVIRONMENT", "development")

    # MuckRock OAuth
    muckrock_client_id: str = os.getenv("MUCKROCK_CLIENT_ID", "")
    muckrock_client_secret: str = os.getenv("MUCKROCK_CLIENT_SECRET", "")
    session_secret: str = os.getenv("SESSION_SECRET", "")
    muckrock_base_url: str = os.getenv("MUCKROCK_BASE_URL", "https://accounts.muckrock.com")
    oauth_redirect_base: str = os.getenv("OAUTH_REDIRECT_BASE", "")  # e.g. http://localhost:5173
    session_max_age: int = int(os.getenv("SESSION_MAX_AGE", str(86400 * 7)))  # 7 days

    # Stripe (license key management)
    stripe_secret_key: str = os.getenv("STRIPE_SECRET_KEY", "")
    stripe_webhook_secret: str = os.getenv("STRIPE_WEBHOOK_SECRET", "")
    stripe_annual_price_id: str = os.getenv("STRIPE_ANNUAL_PRICE_ID", "")

    # Email allowlist — comma-separated emails and/or @domain patterns.
    # Entries starting with @ match any email from that domain (e.g. @muckrock.com).
    # Empty string = no restriction (all MuckRock users allowed).
    email_allowlist: str = os.getenv("EMAIL_ALLOWLIST", "")

    # Admin emails — comma-separated exact emails that receive Pro tier (1,000 credits)
    # regardless of their MuckRock entitlements. Does not downgrade team users.
    # Empty string = no overrides.
    admin_emails: str = os.getenv("ADMIN_EMAILS", "")

    # User Defaults
    default_credits: int = int(os.getenv("DEFAULT_USER_CREDITS", "100"))
    default_timezone: str = os.getenv("DEFAULT_USER_TIMEZONE", "UTC")

    # MuckRock Plan URLs (Sunlight pattern)
    muckrock_pro_plan_url: str = os.getenv(
        "MUCKROCK_PRO_PLAN_URL",
        "https://accounts.muckrock.com/plans/70-cojournalist-pro/"  # Plan ID 70 confirmed by MuckRock 2026-03-25
    )
    muckrock_team_plan_url: str = os.getenv(
        "MUCKROCK_TEAM_PLAN_URL",
        "https://accounts.muckrock.com/plans/71-cojournalist-team/"
    )


    # Firecrawl
    firecrawl_api_key: str = os.getenv("FIRECRAWL_API_KEY", "")

    # Apify
    apify_api_token: str = os.getenv("APIFY_API_TOKEN", "")

    # AWS API Gateway
    aws_api_base_url: str = os.getenv(
        "AWS_API_BASE_URL",
        "https://kubbp7dr0b.execute-api.eu-central-1.amazonaws.com/dev"
    )

    # AWS DynamoDB (for scout embeddings)
    aws_region: str = os.getenv("AWS_DEFAULT_REGION", "eu-central-1")

    # AWS EventBridge Scheduler (for direct scout management via ScheduleService)
    scraper_lambda_arn: str = os.getenv("SCRAPER_LAMBDA_ARN", "")
    eventbridge_role_arn: str = os.getenv("EVENTBRIDGE_ROLE_ARN", "")

    # LLM model — Gemini models (gemini-*) route to Google AI direct API,
    # all others route to OpenRouter. See docs/benchmarks/ for model comparison.
    llm_model: str = os.getenv("LLM_MODEL", "gemini-2.5-flash-lite")

    # Scout service settings
    openrouter_api_key: str = os.getenv("OPENROUTER_API_KEY", "")
    gemini_api_key: str = os.getenv("GEMINI_API_KEY", "")
    resend_api_key: str = os.getenv("RESEND_API_KEY", "")
    internal_service_key: str = os.getenv("INTERNAL_SERVICE_KEY", "")

    # Deployment target — selects adapter set (aws | supabase)
    deployment_target: str = os.getenv("DEPLOYMENT_TARGET", "aws")

    # Supabase / asyncpg
    database_url: str = os.getenv("DATABASE_URL", "")
    supabase_url: str = os.getenv("SUPABASE_URL", "")
    supabase_service_key: str = os.getenv("SUPABASE_SERVICE_KEY", "")
    supabase_anon_key: str = os.getenv("SUPABASE_ANON_KEY", "")
    supabase_jwt_secret: str = os.getenv("SUPABASE_JWT_SECRET", "")

    # Linear (feedback)
    linear_api_key: str = os.getenv("LINEAR_API_KEY", "")

    # CORS — explicit origins only (no wildcards that match unrelated apps)
    allowed_origins: list[str] = [
        "http://localhost:5173",  # SvelteKit dev
        "http://localhost:7860",  # HF Spaces local
        "https://cojournalist.onrender.com",  # Production backend
        "https://cojournalist.ai",  # Production frontend
        "https://www.cojournalist.ai",  # Production frontend (www)
    ]

    class Config:
        env_file = BASE_DIR.parent / ".env"  # Points to root .env file
        case_sensitive = False
        extra = "ignore"  # Ignore extra fields from .env


# Global settings instance
settings = Settings()

# Startup validation — fail fast on bad DEPLOYMENT_TARGET
if settings.deployment_target not in ("aws", "supabase"):
    raise ValueError(
        f"Invalid DEPLOYMENT_TARGET: {settings.deployment_target!r}. "
        "Must be 'aws' or 'supabase'."
    )


def get_settings() -> Settings:
    """Get the global settings instance."""
    return settings
