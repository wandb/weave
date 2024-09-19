import contextlib
import contextvars
import typing
from dataclasses import asdict, dataclass

# Throw an error if op saving encounters an unknonwn condition.
# The default behavior is to warn.
_strict_op_saving: contextvars.ContextVar[bool] = contextvars.ContextVar(
    "_strict_op_saving", default=False
)


def get_strict_op_saving() -> bool:
    return _strict_op_saving.get()


@contextlib.contextmanager
def strict_op_saving(enabled: bool) -> typing.Generator[bool, None, None]:
    token = _strict_op_saving.set(enabled)
    yield _strict_op_saving.get()
    _strict_op_saving.reset(token)


@dataclass
class WandbApiContext:
    user_id: typing.Optional[str] = None
    api_key: typing.Optional[str] = None
    headers: typing.Optional[dict[str, str]] = None
    cookies: typing.Optional[dict[str, str]] = None

    @classmethod
    def from_json(cls, json: typing.Any) -> "WandbApiContext":
        return cls(**json)

    def to_json(self) -> typing.Any:
        return asdict(self)


_wandb_api_context: contextvars.ContextVar[typing.Optional[WandbApiContext]] = (
    contextvars.ContextVar("wandb_api_context", default=None)
)
