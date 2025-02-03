import typing
from .decorator_op import op

RT = typing.TypeVar("RT")


def mutation(f: typing.Callable[..., RT]) -> typing.Callable[..., RT]:
    return op(mutation=True)(f)  # type: ignore
