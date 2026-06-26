"""Runtime configuration for the mock API."""

import os

DEBUG_MODE: bool = os.getenv("DEBUG_MODE", "true").lower() in ("1", "true", "yes")

# Payment timeout: PRD 30 minutes; DEBUG 30 seconds
PAY_TIMEOUT_SECONDS: int = 30 if DEBUG_MODE else 30 * 60

# Fulfillment timeout: PRD 15 minutes; DEBUG 15 seconds
FULFILLMENT_TIMEOUT_SECONDS: int = 15 if DEBUG_MODE else 15 * 60

# Auto-confirm after delivery: PRD next-day 23:59:59; DEBUG 5 seconds
AUTO_CONFIRM_USE_SHORT_DELAY: bool = DEBUG_MODE
AUTO_CONFIRM_DELAY_SECONDS: int = 5 if DEBUG_MODE else 0
