"""Structured, payload-safe metrics for the intent vector store."""

from __future__ import annotations

import json
import logging
import time
from contextlib import contextmanager
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterator

    from pydantic import JsonValue

_logger = logging.getLogger("intent_vector_store.metrics")


def emit(name: str, **fields: JsonValue) -> None:
    payload: dict[str, JsonValue] = {"metric": name, **fields}
    _logger.info("%s", json.dumps(payload, separators=(",", ":"), sort_keys=True))


@contextmanager
def timed(name: str, **fields: JsonValue) -> Iterator[None]:
    started = time.perf_counter()
    outcome = "success"
    try:
        yield
    except Exception:
        outcome = "error"
        raise
    finally:
        emit(
            name,
            duration_ms=round((time.perf_counter() - started) * 1000, 3),
            outcome=outcome,
            **fields,
        )
