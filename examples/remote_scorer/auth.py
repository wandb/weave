"""Bearer-token validation for the remote scorer sample.

This file intentionally contains only a dev validator. Production deployments
should validate tokens with your normal identity provider.
"""

from __future__ import annotations

import hmac
import logging
import os

logger = logging.getLogger(__name__)


def validate_bearer_token(token: str) -> bool:
    """Validate the bearer token sent by Weave.

    This implementation is for local development only. It compares the incoming
    token with REMOTE_SCORER_DEV_BEARER_TOKEN so the sample can run without
    standing up identity infrastructure.

    TODO: Replace this with production validation:
      - validate JWT signature, issuer, audience, expiry, and scope using JWKS;
        or
      - call your identity provider's token introspection endpoint for opaque
        tokens.
    """
    expected = os.environ.get("REMOTE_SCORER_DEV_BEARER_TOKEN")
    if not expected:
        logger.warning(
            "REMOTE_SCORER_DEV_BEARER_TOKEN is not set; rejecting request"
        )
        return False

    return hmac.compare_digest(token, expected)
