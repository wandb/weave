import contextvars
import typing

call_attributes: contextvars.ContextVar[typing.Dict[str, typing.Any]] = (
    contextvars.ContextVar("call_attributes", default={})
)
