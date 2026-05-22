"""SDK-side recovery for HTTP 413 by hoisting oversize call subtrees into refs.

Companion to WB-34652.
"""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, Any

import httpx

if TYPE_CHECKING:
    from weave.trace.weave_client import WeaveClient

logger = logging.getLogger(__name__)

# Subtrees above this threshold get hoisted into their own weave object.
OVERSIZE_SUBTREE_BYTES = 256 * 1024

# Reserved key for the bundled-overflow ref alongside inline survivors.
OVERFLOW_BUNDLE_KEY = "_weave_overflow"


def is_payload_too_large_error(exc: BaseException) -> bool:
    """True iff `exc` is an HTTP 413 (payload too large) error."""
    return (
        isinstance(exc, httpx.HTTPStatusError)
        and exc.response is not None
        and exc.response.status_code == 413
    )


def _approx_size(value: Any) -> int:
    try:
        return len(json.dumps(value, default=str).encode("utf-8"))
    except (TypeError, ValueError):
        return 0


def _safe_name_from_path(path: tuple[str, ...]) -> str:
    parts = [p.replace("/", "_").replace(".", "_") for p in path if p]
    return "_".join(parts) or "call_overflow"


def _publish_subtree(
    value: Any,
    *,
    client: WeaveClient,
    path: tuple[str, ...],
    repackaged: list[str],
) -> str:
    name = _safe_name_from_path(path)
    ref = client._save_object(value, name=name)
    repackaged.append(".".join(path))
    return ref.uri()


def _greedy_batch(
    obj_dict: dict[str, Any],
    *,
    client: WeaveClient,
    path: tuple[str, ...],
    repackaged: list[str],
) -> Any:
    """Smallest-first packing: keep small children inline, bundle the rest into one ref."""
    sized = sorted(
        ((k, v, _approx_size(v)) for k, v in obj_dict.items()),
        key=lambda triple: triple[2],
    )

    inline: dict[str, Any] = {}
    overflow_bundle: dict[str, Any] = {}
    inline_bytes = 0

    for k, v, size in sized:
        if inline_bytes + size <= OVERSIZE_SUBTREE_BYTES:
            inline[k] = v
            inline_bytes += size
        else:
            overflow_bundle[k] = v

    if not overflow_bundle:
        # JSON overhead pushed the parent over the threshold but every child fits.
        return _publish_subtree(obj_dict, client=client, path=path, repackaged=repackaged)

    bundle_ref = _publish_subtree(
        overflow_bundle,
        client=client,
        path=path + (OVERFLOW_BUNDLE_KEY,),
        repackaged=repackaged,
    )
    inline[OVERFLOW_BUNDLE_KEY] = bundle_ref
    return inline


def _walk_and_repackage(
    obj: Any,
    *,
    client: WeaveClient,
    path: tuple[str, ...],
    repackaged: list[str],
) -> Any:
    """Recurse into dicts hoisting oversize children, then greedy-batch the rest."""
    if _approx_size(obj) <= OVERSIZE_SUBTREE_BYTES:
        return obj

    if isinstance(obj, dict):
        new_obj: dict[str, Any] = {}
        for k, v in obj.items():
            new_obj[k] = _walk_and_repackage(
                v,
                client=client,
                path=path + (str(k),),
                repackaged=repackaged,
            )
        if _approx_size(new_obj) <= OVERSIZE_SUBTREE_BYTES:
            return new_obj
        return _greedy_batch(new_obj, client=client, path=path, repackaged=repackaged)

    return _publish_subtree(obj, client=client, path=path, repackaged=repackaged)


def repackage_call_fields(
    client: WeaveClient,
    *,
    fields: dict[str, Any],
) -> tuple[dict[str, Any], list[str]]:
    """Walk each named value in `fields`, hoisting oversize subtrees into refs."""
    repackaged: list[str] = []
    new_fields: dict[str, Any] = {}
    for name, value in fields.items():
        if value is None:
            new_fields[name] = None
            continue
        new_fields[name] = _walk_and_repackage(
            value, client=client, path=(name,), repackaged=repackaged
        )
    return new_fields, repackaged


def emit_user_warning(repackaged_paths: list[str]) -> None:
    """One concise warning naming the fields that were repackaged."""
    if not repackaged_paths:
        return
    logger.warning(
        "weave: call payload exceeded the server size limit; "
        "automatically repackaged %d field(s) into refs: %s. "
        "To avoid this overhead, publish large artifacts upfront with "
        "weave.publish(...) before they enter call inputs/outputs/summary.",
        len(repackaged_paths),
        ", ".join(repackaged_paths),
    )
