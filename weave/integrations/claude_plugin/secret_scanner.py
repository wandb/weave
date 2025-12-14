"""Secret scanning and redaction for Claude plugin.

Scans file content and session transcripts for secrets before uploading to Weave.
Uses detect-secrets library with custom patterns for AI provider API keys.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)

# Check if detect-secrets is available
try:
    from detect_secrets.core.secrets_collection import SecretsCollection
    from detect_secrets.settings import transient_settings

    DETECT_SECRETS_AVAILABLE = True
except ImportError:
    DETECT_SECRETS_AVAILABLE = False
    logger.debug("detect-secrets not installed, secret scanning disabled")


@dataclass
class DetectedSecret:
    """A detected secret with location info."""

    secret_type: str
    line_number: int
    column_start: int
    column_end: int
    secret_value: str


class SecretScanner:
    """Scans text content for secrets and provides redaction."""

    # Default detect-secrets plugins to use
    DEFAULT_PLUGINS = [
        {"name": "AWSKeyDetector"},
        {"name": "AzureStorageKeyDetector"},
        {"name": "BasicAuthDetector"},
        {"name": "GitHubTokenDetector"},
        {"name": "PrivateKeyDetector"},
        {"name": "SlackDetector"},
        {"name": "StripeDetector"},
        {"name": "TwilioKeyDetector"},
        {"name": "HighEntropyString", "limit": 4.5},
    ]

    # Custom patterns for AI provider keys (not in detect-secrets by default)
    AI_PROVIDER_PATTERNS = [
        # OpenAI - sk-... or sk-proj-...
        (r"sk-(?:proj-)?[A-Za-z0-9_-]{20,}", "openai_api_key"),
        # Anthropic - sk-ant-...
        (r"sk-ant-[A-Za-z0-9_-]{20,}", "anthropic_api_key"),
        # Google AI / Gemini - AIza...
        (r"AIza[A-Za-z0-9_-]{35}", "google_api_key"),
        # HuggingFace - hf_...
        (r"hf_[A-Za-z0-9]{34}", "huggingface_token"),
        # Replicate - r8_...
        (r"r8_[A-Za-z0-9]{40}", "replicate_api_key"),
        # Cohere - context-sensitive
        (r"(?:COHERE_API_KEY|cohere_api_key)\s*[=:]\s*['\"]?([A-Za-z0-9]{40})['\"]?", "cohere_api_key"),
        # Mistral - context-sensitive
        (r"(?:MISTRAL_API_KEY|mistral_api_key)\s*[=:]\s*['\"]?([A-Za-z0-9]{32})['\"]?", "mistral_api_key"),
    ]

    def __init__(self) -> None:
        """Initialize the scanner."""
        self._ai_patterns = [
            (re.compile(pattern), name) for pattern, name in self.AI_PROVIDER_PATTERNS
        ]

    def scan_text(self, content: str, filename: str = "content") -> list[DetectedSecret]:
        """Scan text for secrets using detect-secrets and custom patterns.

        Args:
            content: Text content to scan
            filename: Filename for context (used by detect-secrets)

        Returns:
            List of detected secrets with locations
        """
        secrets: list[DetectedSecret] = []

        # Use detect-secrets if available
        if DETECT_SECRETS_AVAILABLE:
            secrets.extend(self._scan_with_detect_secrets(content, filename))

        # Always scan with custom AI provider patterns
        secrets.extend(self._scan_ai_patterns(content))

        return secrets

    def _scan_with_detect_secrets(
        self, content: str, filename: str
    ) -> list[DetectedSecret]:
        """Scan using detect-secrets library."""
        import io

        secrets: list[DetectedSecret] = []

        with transient_settings({"plugins_used": self.DEFAULT_PLUGINS}):
            collection = SecretsCollection()
            collection.scan_file(io.StringIO(content), filename)

            for secret in collection[filename]:
                secrets.append(
                    DetectedSecret(
                        secret_type=secret.type,
                        line_number=secret.line_number,
                        column_start=0,  # detect-secrets doesn't provide column
                        column_end=0,
                        secret_value=secret.secret_value or "",
                    )
                )

        return secrets

    def _scan_ai_patterns(self, content: str) -> list[DetectedSecret]:
        """Scan for AI provider API keys using custom patterns."""
        secrets: list[DetectedSecret] = []
        lines = content.split("\n")

        for line_num, line in enumerate(lines, start=1):
            for pattern, secret_type in self._ai_patterns:
                for match in pattern.finditer(line):
                    # Get the actual secret value (use group 1 if exists, else group 0)
                    secret_value = match.group(1) if match.lastindex else match.group(0)
                    secrets.append(
                        DetectedSecret(
                            secret_type=secret_type,
                            line_number=line_num,
                            column_start=match.start(),
                            column_end=match.end(),
                            secret_value=secret_value,
                        )
                    )

        return secrets


# Module-level scanner instance (lazy initialized)
_scanner: SecretScanner | None = None


def get_secret_scanner() -> SecretScanner | None:
    """Get the singleton SecretScanner instance.

    Returns None if detect-secrets is not installed and we have no fallback.
    """
    global _scanner

    if _scanner is not None:
        return _scanner

    # We can still scan with just AI patterns even without detect-secrets
    _scanner = SecretScanner()
    return _scanner
