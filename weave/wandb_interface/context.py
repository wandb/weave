# Context management for W&B API without dependencies on compat layer

from __future__ import annotations

from contextvars import ContextVar
from dataclasses import asdict, dataclass
from typing import Any

from typing_extensions import Self


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


def get_wandb_api_context() -> WandbApiContext | None:
    return _wandb_api_context.get(None)


def init() -> None:
    """Read auth from environment and set the context (if not already set)."""
    if get_wandb_api_context() is not None:
        return
    from weave.trace import env

    if api_key := env.weave_wandb_api_key():
        _wandb_api_context.set(WandbApiContext(api_key=api_key))
