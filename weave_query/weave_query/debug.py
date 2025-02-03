import typing

# Debugging tools


def trace(fn: typing.Callable) -> typing.Callable:
    """Decorator for tracing recursive function calls."""

    ctx = {"level": 0}

    def traced_fn(*args: typing.Any, **kwargs: typing.Any) -> typing.Any:
        level = ctx["level"]
        print("  " * level, "calling", fn.__name__, "with", args, kwargs)
        ctx["level"] += 1
        result = fn(*args, **kwargs)
        ctx["level"] -= 1
        print("  " * level, "result", result)
        return result

    return traced_fn
