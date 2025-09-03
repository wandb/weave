# Context management for W&B API without dependencies on compat layer

from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager
from contextvars import ContextVar, Token
from dataclasses import asdict, dataclass
from typing import Any

from typing_extensions import Self

from weave.trace import env


@dataclass
class WandbApiContext:
    user_id: str | None = None  # TODO: delete
    api_key: str | None = None
    headers: dict[str, str] | None = None  # TODO: delete
    cookies: dict[str, str] | None = None  # TODO: delete

    @classmethod
    def from_json(cls, json: dict[str, Any]) -> Self:
        return cls(**json)

    def to_json(self) -> dict[str, Any]:
        return asdict(self)


_wandb_api_context: ContextVar[WandbApiContext | None] = ContextVar("wandb_api_context")


def set_wandb_thread_local_api_settings(
    api_key: str | None,
    cookies: dict[str, str] | None,
    headers: dict[str, str] | None,
) -> None:
    try:
        from wandb.sdk.internal.internal_api import _thread_local_api_settings

        _thread_local_api_settings.api_key = api_key
        _thread_local_api_settings.cookies = cookies
        _thread_local_api_settings.headers = headers
    except ImportError:
        # wandb not available, that's fine
        pass


def set_wandb_api_context(
    user_id: str | None,
    api_key: str | None,
    headers: dict[str, str] | None,
    cookies: dict[str, str] | None,
) -> Token[WandbApiContext | None] | None:
    if get_wandb_api_context():
        # WANDB API context is only allowed to be set once per thread, since we
        # need to use thread local storage to communicate the context to the wandb
        # lib right now.
        return None
    set_wandb_thread_local_api_settings(api_key, cookies, headers)
    return _wandb_api_context.set(WandbApiContext(user_id, api_key, headers, cookies))


def reset_wandb_api_context(token: Token[WandbApiContext | None]) -> None:
    if token is None:
        return
    set_wandb_thread_local_api_settings(None, None, None)
    _wandb_api_context.reset(token)


def get_wandb_api_context() -> WandbApiContext | None:
    return _wandb_api_context.get(None)


def init() -> Token[WandbApiContext | None] | None:
    if api_key := env.weave_wandb_api_key():
        return set_wandb_api_context("admin", api_key, None, None)
    return None


@contextmanager
def from_environment() -> Generator[None]:
    token = init()
    try:
        yield
    finally:
        if token:
            reset_wandb_api_context(token)
