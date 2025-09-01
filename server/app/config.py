"""
Configuration module for environment variables.

Reads various environment variables for Account Aggregator (AA) configuration,
sync settings, and other application configuration.
"""

import os

# Development Configuration
DEV_MODE = os.getenv("DEV_MODE", "false").lower() == "true"

# Development Configuration
DEV_MODE = os.getenv("DEV_MODE", "false").lower() == "true"

# Account Aggregator Configuration
USE_REAL_AA = os.getenv("USE_REAL_AA", "false").lower() == "true"
AA_BASE_URL = os.getenv("AA_BASE_URL", "")
AA_API_KEY = os.getenv("AA_API_KEY", "")
AA_SECRET = os.getenv("AA_SECRET", "")

# Mock webhook configuration
AA_MOCK_WEBHOOK_SECRET = os.getenv("AA_MOCK_WEBHOOK_SECRET", "")

# Sync Configuration
SYNC_BATCH_SIZE = int(os.getenv("SYNC_BATCH_SIZE", "100"))
SYNC_POLL_INTERVAL = int(os.getenv("SYNC_POLL_INTERVAL", "30"))


def is_real_aa() -> bool:
    """
    Returns True if the application should use real Account Aggregator,
    False if it should use mock/test mode.

    Returns:
        bool: True if USE_REAL_AA environment variable is set to "true" (case-insensitive)
    """
    return USE_REAL_AA


def is_dev_mode() -> bool:
    """
    Returns True if the application is running in development mode.
    """
    return DEV_MODE


def is_dev_mode() -> bool:
    """
    Returns True if the application is running in development mode.
    """
    return DEV_MODE