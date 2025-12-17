"""Claude Code credentials management.

This module provides utilities for retrieving Claude Code OAuth credentials
from the system, enabling API calls using the same authentication as the
Claude Code CLI.

Credential sources (in order of priority):
1. ~/.claude/.credentials.json (legacy/cross-platform)
2. macOS Keychain (via `security` command)

The OAuth tokens require the beta header "anthropic-beta: oauth-2025-04-20"
to work with the Anthropic API.
"""

from __future__ import annotations

import json
import logging
import platform
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# The beta header that enables OAuth authentication
OAUTH_BETA_HEADER = "oauth-2025-04-20"

# Credentials file path (legacy location)
CREDENTIALS_FILE = Path.home() / ".claude" / ".credentials.json"


@dataclass
class OAuthCredentials:
    """OAuth credentials for Claude Code API access.

    Attributes:
        access_token: The OAuth access token (sk-ant-oat01-...)
        refresh_token: Token for refreshing when expired
        expires_at: Expiration timestamp in milliseconds
        subscription_type: User's subscription (e.g., "max", "pro")
        rate_limit_tier: Rate limit tier info
        scopes: OAuth scopes granted
    """

    access_token: str
    refresh_token: str | None = None
    expires_at: int | None = None
    subscription_type: str | None = None
    rate_limit_tier: str | None = None
    scopes: list[str] | None = None

    @property
    def is_expired(self) -> bool:
        """Check if the access token is expired."""
        if self.expires_at is None:
            return False
        # expires_at is in milliseconds
        return time.time() * 1000 > self.expires_at

    @property
    def expires_in_hours(self) -> float | None:
        """Get hours until token expires, or None if no expiry."""
        if self.expires_at is None:
            return None
        remaining_ms = self.expires_at - (time.time() * 1000)
        return remaining_ms / 1000 / 60 / 60


def _load_credentials_from_file() -> dict[str, Any] | None:
    """Load credentials from ~/.claude/.credentials.json.

    Returns:
        Parsed credentials dict or None if not found/invalid
    """
    if not CREDENTIALS_FILE.exists():
        return None

    try:
        with open(CREDENTIALS_FILE) as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        logger.debug(f"Failed to load credentials file: {e}")
        return None


def _load_credentials_from_keychain() -> dict[str, Any] | None:
    """Load credentials from macOS Keychain.

    Returns:
        Parsed credentials dict or None if not found/invalid
    """
    if platform.system() != "Darwin":
        return None

    try:
        result = subprocess.run(
            [
                "security",
                "find-generic-password",
                "-s",
                "Claude Code-credentials",
                "-w",
            ],
            capture_output=True,
            text=True,
            check=True,
            timeout=5,
        )

        return json.loads(result.stdout.strip())
    except subprocess.CalledProcessError:
        logger.debug("No Claude Code credentials found in keychain")
        return None
    except subprocess.TimeoutExpired:
        logger.debug("Keychain access timed out")
        return None
    except json.JSONDecodeError as e:
        logger.debug(f"Failed to parse keychain credentials: {e}")
        return None


def get_oauth_credentials() -> OAuthCredentials | None:
    """Get Claude Code OAuth credentials.

    Tries to load credentials from:
    1. ~/.claude/.credentials.json (legacy/cross-platform)
    2. macOS Keychain (if on macOS)

    Returns:
        OAuthCredentials if found, None otherwise
    """
    # Try credentials file first
    creds = _load_credentials_from_file()

    # Fall back to keychain on macOS
    if creds is None:
        creds = _load_credentials_from_keychain()

    if creds is None:
        return None

    # Extract OAuth info from credentials
    # Structure: {"claudeAiOauth": {"accessToken": ..., ...}}
    oauth_data = creds.get("claudeAiOauth")
    if not oauth_data:
        logger.debug("Credentials found but no claudeAiOauth section")
        return None

    access_token = oauth_data.get("accessToken")
    if not access_token:
        logger.debug("No access token in OAuth credentials")
        return None

    return OAuthCredentials(
        access_token=access_token,
        refresh_token=oauth_data.get("refreshToken"),
        expires_at=oauth_data.get("expiresAt"),
        subscription_type=oauth_data.get("subscriptionType"),
        rate_limit_tier=oauth_data.get("rateLimitTier"),
        scopes=oauth_data.get("scopes"),
    )


def get_api_headers(credentials: OAuthCredentials) -> dict[str, str]:
    """Get HTTP headers for Anthropic API calls using OAuth.

    Args:
        credentials: OAuth credentials

    Returns:
        Dict of headers to use with requests
    """
    return {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {credentials.access_token}",
        "anthropic-version": "2023-06-01",
        "anthropic-beta": OAUTH_BETA_HEADER,
    }
