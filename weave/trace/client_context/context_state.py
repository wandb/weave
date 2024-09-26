import contextvars

# Throw an error if op saving encounters an unknonwn condition.
# The default behavior is to warn.
_strict_op_saving: contextvars.ContextVar[bool] = contextvars.ContextVar(
    "_strict_op_saving", default=False
)


def get_strict_op_saving() -> bool:
    return _strict_op_saving.get()
