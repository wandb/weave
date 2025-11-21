from collections.abc import Generator
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Protocol


class SecretFetcher(Protocol):
    def fetch(self, secret_name: str) -> dict: ...


_secret_fetcher_context: ContextVar[SecretFetcher | None] = ContextVar(
    "secret_fetcher", default=None
)


@contextmanager
def secret_fetcher_context(sf: SecretFetcher) -> Generator[None, None, None]:
    token = _secret_fetcher_context.set(sf)
    try:
        yield
    finally:
        _secret_fetcher_context.reset(token)
