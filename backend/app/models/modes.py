"""
Mode definitions and enums.

PURPOSE: Literal types and enums shared across request models and services
for scout type, schedule regularity, and monitoring channel.

DEPENDS ON: (stdlib only)
USED BY: models/responses.py, schemas/pulse.py, services/cron.py,
    routers/pulse.py
"""
from enum import Enum
from typing import Literal


# Scraper regularity types
RegularityType = Literal["daily", "weekly", "monthly"]

# Monitoring types
MonitoringType = Literal["EMAIL", "SMS", "WEBHOOK"]

# Scout types for different monitoring strategies
ScoutType = Literal["web", "pulse", "social", "civic"]

# Social media monitoring types
SocialPlatform = Literal["instagram", "x", "facebook"]
SocialMonitorMode = Literal["summarize", "criteria"]


class ScoutMode(str, Enum):
    """Scout execution mode for local news features."""
    PULSE = "pulse"  # Local Pulse - no custom prompt, daily digest
