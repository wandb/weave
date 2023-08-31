import json
import typing
import copy

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


# This should only be called in two places. In use_json above,
# and in mappers_gql.py in the GQLStringToString mapper.
def cache_json(key: str, value: typing.Any) -> None:
    gql_json_cache()[key] = value
