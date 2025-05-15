from logging import getLogger
from typing import Any

logger = getLogger("weave")


def weave_print(*args: Any, **kwargs: Any) -> None:
    should_print = True
    if not should_print:
        return
    return print(*args, **kwargs)  # noqa: T201
