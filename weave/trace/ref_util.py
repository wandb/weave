from __future__ import annotations

import logging
from collections.abc import Callable
from concurrent.futures import Future
from typing import Any

from weave.trace.refs import ObjectRef, Ref

logger = logging.getLogger(__name__)


def get_ref(obj: Any) -> ObjectRef | None:
    return getattr(obj, "ref", None)


def remove_ref(obj: Any) -> None:
    if get_ref(obj) is not None:
        if "ref" in obj.__dict__:  # for methods
            obj.__dict__["ref"] = None
        else:
            obj.ref = None


def set_ref(obj: Any, ref: Ref | None) -> None:
    """Try to set the ref on "any" object.

    We use increasingly complex methods to try to set the ref
    to support different kinds of objects. This will still
    fail for python primitives, but those can't be traced anyway.
    """
    try:
        obj.ref = ref
    except Exception:
        try:
            obj.__dict__["ref"] = ref
        except Exception:
            logger.debug(
                "set_ref: could not attach ref to object of type %s",
                type(obj).__name__,
            )
            raise ValueError(
                f"Failed to set ref on object of type {type(obj)}"
            ) from None


def clear_refs_on_failure(
    digest_future: Future[str], cleanup: Callable[[], None]
) -> None:
    """Run `cleanup` if `digest_future` resolves with an exception.

    A failed digest_future retains the serialized payload via its exception
    traceback's frame locals — anything still referencing the Ref (whose
    `_digest` is the future) pins that payload. Callers register a cleanup
    that breaks the reference path from user objects to the Ref.
    """

    def _on_done(fut: Future[str]) -> None:
        if fut.exception() is None:
            return
        try:
            cleanup()
        except Exception as e:
            logger.debug("clear_refs_on_failure cleanup raised: %s", e)

    digest_future.add_done_callback(_on_done)
