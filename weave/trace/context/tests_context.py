import contextlib
import contextvars
from collections.abc import Generator

test_only_raise_on_captured_errors: contextvars.ContextVar[bool] = (
    contextvars.ContextVar("test_only_raise_on_captured_errors", default=False)
)


@contextlib.contextmanager
def raise_on_captured_errors(should_raise: bool = True) -> Generator[None, None, None]:
    token = test_only_raise_on_captured_errors.set(should_raise)
    try:
        yield
    finally:
        test_only_raise_on_captured_errors.reset(token)


def get_raise_on_captured_errors() -> bool:
    return test_only_raise_on_captured_errors.get(False)
