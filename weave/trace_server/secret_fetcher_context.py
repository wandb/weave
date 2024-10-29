import contextvars
from typing import Optional, Protocol


class SecretFetcher(Protocol):
    def fetch(self, secret_name: str) -> dict: ...


_secret_fetcher_context: contextvars.ContextVar[Optional[SecretFetcher]] = (
    contextvars.ContextVar("secret_fetcher", default=None)
)
