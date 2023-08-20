import json
import typing
from typing import Any

import contextvars
import contextlib

# This file contains a context manager for managing the state of the gql json cache.
# The GQL client automatically deserializes json responses into python objects.
# In weave, we type and store arbitrary json blobs as strings. This context manager
# allows us to use cache the deserialized python objects that the GQL client automatically
# produces, so that we can avoid deserializing the same json blob multiple times.


# This context var is used to store the json cache. It maps the serialized json string
# to the deserialized python object.
_GQL_JSON_CACHE: contextvars.ContextVar[dict[str, typing.Any]] = contextvars.ContextVar(
    "gql_json_cache", default={}
)


# These classes are used to ensure that cached values are not modified.
# This is necessary because some ops read from the cache and then modify the
# returned value. If the value is cached, then the modification will be visible
# to other ops that read from the cache.

# To get around this, we use these immutable classes to wrap the cached values.
# This ensures that the cached values are not modified. If an op needs to modify
# a cached value, it should first unfrozen() the value, which will return a mutable
# copy of the value. The op can then modify the copy and the cache will not be affected.


def immutable_error_message(self: Any, args: Any, kwargs: Any) -> str:
    return (
        f"Cannot modify {self} with args: {args} kwargs: {kwargs}. Object is immutable."
    )


class ImmutableDict(dict):
    def update(self, *args: Any, **kwargs: Any) -> None:
        raise TypeError(immutable_error_message(self, args, kwargs))

    def popitem(self, *args: Any, **kwargs: Any) -> Any:
        raise TypeError(immutable_error_message(self, args, kwargs))

    def setdefault(self, *args: Any, **kwargs: Any) -> None:
        raise TypeError(immutable_error_message(self, args, kwargs))

    def pop(self, *args: Any, **kwargs: Any) -> Any:
        raise TypeError(immutable_error_message(self, args, kwargs))

    def __setitem__(self, *args: Any, **kwargs: Any) -> None:
        raise TypeError(immutable_error_message(self, args, kwargs))

    def __delitem__(self, *args: Any, **kwargs: Any) -> None:
        raise TypeError(immutable_error_message(self, args, kwargs))

    def __repr__(self) -> str:
        return "ImmutableDict(" + super().__repr__() + ")"


class ImmutableList(list):
    def append(self, *args: Any, **kwargs: Any) -> None:
        raise TypeError(immutable_error_message(self, args, kwargs))

    def extend(self, *args: Any, **kwargs: Any) -> None:
        raise TypeError(immutable_error_message(self, args, kwargs))

    def insert(self, *args: Any, **kwargs: Any) -> None:
        raise TypeError(immutable_error_message(self, args, kwargs))

    def remove(self, *args: Any, **kwargs: Any) -> None:
        raise TypeError(immutable_error_message(self, args, kwargs))

    def sort(self, *args: Any, **kwargs: Any) -> None:
        raise TypeError(immutable_error_message(self, args, kwargs))

    def reverse(self, *args: Any, **kwargs: Any) -> None:
        raise TypeError(immutable_error_message(self, args, kwargs))

    def pop(self, *args: Any, **kwargs: Any) -> Any:
        raise TypeError(immutable_error_message(self, args, kwargs))

    def __setitem__(self, *args: Any, **kwargs: Any) -> None:
        raise TypeError(immutable_error_message(self, args, kwargs))

    def __delitem__(self, *args: Any, **kwargs: Any) -> None:
        raise TypeError(immutable_error_message(self, args, kwargs))

    def __repr__(self) -> str:
        return "ImmutableList(" + super().__repr__() + ")"


def frozen(obj: Any) -> Any:
    if isinstance(obj, dict):
        return ImmutableDict({key: frozen(value) for key, value in obj.items()})
    elif isinstance(obj, list):
        return ImmutableList(frozen(v) for v in obj)
    return obj


def unfrozen(data: Any) -> Any:
    if isinstance(data, dict):
        return {key: unfrozen(value) for key, value in data.items()}
    elif isinstance(data, list):
        return [unfrozen(value) for value in data]
    else:
        return data


@contextlib.contextmanager
def gql_json_cache_context() -> typing.Iterator[None]:
    token = _GQL_JSON_CACHE.set({})
    try:
        yield
    finally:
        _GQL_JSON_CACHE.get().clear()
        _GQL_JSON_CACHE.reset(token)


def gql_json_cache() -> dict[str, typing.Any]:
    return _GQL_JSON_CACHE.get()


# This is the entry point for reading from the json cache.
# If the key is not in the cache, it will be deserialized and added to the cache.
def use_json(key: str) -> typing.Any:
    cache = gql_json_cache()
    result = cache.get(key, None)
    if result is None:
        result = json.loads(key)
        cache_json(key, result)
    return result


def cache_json(key: str, value: typing.Any) -> None:
    gql_json_cache()[key] = frozen(value)
