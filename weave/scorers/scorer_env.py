"""
This file provides a common interface for scorers to get API keys. Using
`getenv`, the scorer can fetch the API key from the secret fetcher context
when running remotely and from the environment when running locally.
"""

import os
import typing

from weave.trace_server.secret_fetcher_context import _secret_fetcher_context


def getenv(key: str, default: typing.Optional[str] = None) -> typing.Optional[str]:
    secret_fetcher = _secret_fetcher_context.get()
    if secret_fetcher:
        return secret_fetcher.fetch(key).get("secrets", {}).get(key, default)
    return os.environ.get(key, default)
