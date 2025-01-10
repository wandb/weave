import contextvars
from collections.abc import Generator
from contextlib import contextmanager
from typing import Optional, Protocol


class SecretFetcher(Protocol):
    def fetch(self, secret_name: str) -> dict: ...


_secret_fetcher_context: contextvars.ContextVar[Optional[SecretFetcher]] = (
    contextvars.ContextVar("secret_fetcher", default=None)
)


@contextmanager
def secret_fetcher_context(sf: SecretFetcher) -> Generator[None, None, None]:
    token = _secret_fetcher_context.set(sf)
    try:
        yield
    finally:
        _secret_fetcher_context.reset(token)
