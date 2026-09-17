"""Turn a request model into keyword arguments the vendored client accepts.

The client under `weave/vendor/weave_server_sdk/` is generated in wandb/core and lands
here one sync behind this repository, so a field just added to a request model has no
parameter on the generated method yet. Splatting the model dump into that method raises
`TypeError` before any HTTP call is made, and because the dump carries defaults it
raises for callers that never set the field. `build_request_kwargs` keeps such a field
on the wire by moving it into `extra_body`, which the server reads like a declared field.
"""

from __future__ import annotations

import functools
import inspect
from collections.abc import Callable
from typing import Any

from pydantic import BaseModel

# Signature parameters that are never request fields. `self` comes from reading the plain
# function; a field named `timeout` would reach httpx instead of the server.
NOT_BODY_PARAMS = frozenset(
    {"self", "extra_headers", "extra_query", "extra_body", "timeout", "accept"}
)

# Generated methods whose route is a GET, where `_base_client.py` allows no body at all.
NO_BODY_METHODS = frozenset(
    {
        "TagsResource.list",
        "AliasesResource.list",
        "AnnotationQueuesResource.read",
    }
)


class UnsendableFieldError(Exception):
    """Raised when a request field has no way to reach the server."""


@functools.cache
def _declared_params(func: Callable[..., Any]) -> frozenset[str]:
    """Request fields the generated method declares.

    Keyed on the plain function because `_update_client_headers` copies the client, so a
    bound method of the new resource object would miss, and the cache would keep the old
    one alive.
    """
    return frozenset(inspect.signature(func).parameters) - NOT_BODY_PARAMS


def build_request_kwargs(
    req: BaseModel, api: Callable[..., Any], **dump_kwargs: Any
) -> dict[str, Any]:
    """Dump `req` into keyword arguments for `api`, routing the rest to `extra_body`.

    The callsite's own `exclude` and `exclude_none` reach `model_dump` unchanged. The
    overflow is dumped again in JSON mode, because `extra_body` is serialised by a plain
    JSON encoder rather than by the vendor's `maybe_transform`. That second dump selects
    by field name while the split reads dumped keys, so a field renamed by an alias would
    go unnoticed here.
    """
    dumped = req.model_dump(**dump_kwargs)
    declared = _declared_params(getattr(api, "__func__", api))
    overflow_keys = {key for key in dumped if key not in declared}
    if not overflow_keys:
        return dumped

    qualname = getattr(api, "__qualname__", "")
    if qualname in NO_BODY_METHODS:
        raise UnsendableFieldError(
            f"{type(req).__name__} has fields {sorted(overflow_keys)} that "
            f"{qualname} does not declare, and that route is a GET, where the vendored "
            f"client sends no body. Regenerate the client in wandb/core and re-vendor "
            f"it, or send the fields in the query string instead."
        )

    kwargs = {key: value for key, value in dumped.items() if key not in overflow_keys}
    kwargs["extra_body"] = req.model_dump(
        mode="json", include=overflow_keys, **dump_kwargs
    )
    return kwargs
