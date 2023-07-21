# Official interface for interacting with the W&B API. All
# Weave interactions with the Weave API should go through this
# module.

import dataclasses
import typing
import contextvars


@dataclasses.dataclass
class WandbApiContext:
    user_id: typing.Optional[str] = None
    api_key: typing.Optional[str] = None
    headers: typing.Optional[dict[str, str]] = None
    cookies: typing.Optional[dict[str, str]] = None

    @classmethod
    def from_json(cls, json: typing.Any) -> "WandbApiContext":
        return cls(**json)

    def to_json(self) -> typing.Any:
        return dataclasses.asdict(self)


## wandb_api.py context
_wandb_api_context: contextvars.ContextVar[
    typing.Optional[WandbApiContext]
] = contextvars.ContextVar("_weave_api_context", default=None)
