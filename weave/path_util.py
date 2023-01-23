import pathlib
import typing

from . import errors


def safe_join(*args: typing.Union[str, pathlib.Path]) -> str:
    # Ensure result is relative to first dir.
    first_part = pathlib.Path(args[0])
    result = first_part.joinpath(*args[1:])
    if not result.resolve().is_relative_to(first_part.resolve()):
        raise errors.WeaveAccessDeniedError()
    return str(result)
