"""Session title generation using Claude API.

This module replicates Claude Code CLI's session naming logic, using the
same credentials and API endpoint to generate session titles.

The API call uses:
- Model: claude-3-5-haiku-latest (small, fast)
- Temperature: 0 (deterministic)
- Max tokens: 512
- OAuth authentication with anthropic-beta: oauth-2025-04-20
"""

from __future__ import annotations

import json
import logging

logger = logging.getLogger(__name__)

# System prompt from Claude Code CLI (NT2 function)
SESSION_TITLE_SYSTEM_PROMPT = (
    "Analyze if this message indicates a new conversation topic. "
    "If it does, extract a 2-3 word title that captures the new topic. "
    "Format your response as a JSON object with two fields: 'isNewTopic' "
    "(boolean) and 'title' (string, or null if isNewTopic is false). "
    "Only include these fields, no other text."
)


def analyze_session_title(
    user_message: str,
    access_token: str,
    model: str = "claude-3-5-haiku-latest",
    timeout: float = 30.0,
) -> tuple[bool, str | None]:
    """Analyze if a user message indicates a new topic and extract title.

    Uses the same logic as Claude Code CLI's NT2 function.

    Args:
        user_message: The user's message to analyze
        access_token: OAuth access token (sk-ant-oat01-...)
        model: Model to use (default: claude-3-5-haiku-latest)
        timeout: Request timeout in seconds

    Returns:
        Tuple of (is_new_topic, title).
        - is_new_topic: True if the message establishes a topic
        - title: 2-3 word title if is_new_topic, else None
    """
    # Import here to avoid dependency issues if requests not installed
    try:
        import requests
    except ImportError:
        logger.debug("requests not installed, cannot analyze session title")
        return False, None

    # Skip local command output (same as CLI)
    if user_message.startswith("<local-command-stdout>"):
        return False, None

    from weave.integrations.claude_plugin.credentials import (
        OAUTH_BETA_HEADER,
    )

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {access_token}",
        "anthropic-version": "2023-06-01",
        "anthropic-beta": OAUTH_BETA_HEADER,
    }

    payload = {
        "model": model,
        "max_tokens": 512,
        "temperature": 0,
        "system": SESSION_TITLE_SYSTEM_PROMPT,
        "messages": [{"role": "user", "content": user_message}],
    }

    try:
        response = requests.post(
            "https://api.anthropic.com/v1/messages?beta=true",
            headers=headers,
            json=payload,
            timeout=timeout,
        )

        if not response.ok:
            logger.debug(f"API error {response.status_code}: {response.text}")
            return False, None

        result = response.json()

        # Extract text content from response
        text_content = "".join(
            block["text"]
            for block in result.get("content", [])
            if block.get("type") == "text"
        )

        # Parse JSON response
        parsed = json.loads(text_content)
        if (
            isinstance(parsed, dict)
            and "isNewTopic" in parsed
            and "title" in parsed
            and parsed["isNewTopic"]
            and parsed["title"]
        ):
            return True, str(parsed["title"])

    except requests.exceptions.Timeout:
        logger.debug("Session title API call timed out")
    except requests.exceptions.RequestException as e:
        logger.debug(f"Session title API request failed: {e}")
    except json.JSONDecodeError as e:
        logger.debug(f"Failed to parse session title response: {e}")
    except Exception as e:
        logger.debug(f"Unexpected error in session title analysis: {e}")

    return False, None


def generate_session_title(
    user_message: str,
    access_token: str | None = None,
    model: str = "claude-3-5-haiku-latest",
    timeout: float = 10.0,
) -> str | None:
    """Generate a session title from the user's first message.

    Convenience wrapper around analyze_session_title that:
    1. Attempts to get credentials if not provided
    2. Handles the is_new_topic logic
    3. Returns just the title or None

    Args:
        user_message: The user's message to analyze
        access_token: OAuth access token (optional, will try to get from system)
        model: Model to use
        timeout: Request timeout in seconds

    Returns:
        Session title string, or None if generation failed
    """
    # Get credentials if not provided
    if access_token is None:
        from weave.integrations.claude_plugin.credentials import (
            get_oauth_credentials,
        )

        creds = get_oauth_credentials()
        if creds is None:
            logger.debug("No OAuth credentials available for session title")
            return None

        if creds.is_expired:
            logger.debug("OAuth token expired, cannot generate session title")
            return None

        access_token = creds.access_token

    is_new_topic, title = analyze_session_title(
        user_message, access_token, model=model, timeout=timeout
    )

    if is_new_topic and title:
        return title

    return None
