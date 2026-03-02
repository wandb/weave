from __future__ import annotations

import json
import logging
import threading
import time
from typing import Any, Protocol

from pydantic import BaseModel

logger = logging.getLogger(__name__)


class TraceRequestWriter(Protocol):
    """Protocol for writing trace server requests to a storage backend.

    Implementations handle serialization and persistence of trace server
    method calls. Examples include JSONL files, SQLite databases, etc.
    """

    def write_request(
        self,
        method: str,
        args: tuple[Any, ...],
        kwargs: dict[str, Any],
    ) -> None: ...


def _serialize_arg(arg: Any) -> Any:
    """Serialize a single argument for storage."""
    if isinstance(arg, BaseModel):
        return arg.model_dump(mode="json")
    return arg


class JsonlRequestWriter:
    """Writes trace server requests as JSON Lines to a file.

    Each call to write_request appends one JSON line containing the timestamp,
    method name, and serialized request data. Thread-safe via a lock around
    file writes. Errors are logged but never raised.
    """

    def __init__(self, file_path: str) -> None:
        self._file_path = file_path
        self._write_lock = threading.Lock()

    def write_request(
        self,
        method: str,
        args: tuple[Any, ...],
        kwargs: dict[str, Any],
    ) -> None:
        try:
            record: dict[str, Any] = {
                "timestamp": time.time(),
                "method": method,
            }

            if args:
                record["args"] = [_serialize_arg(a) for a in args]
            if kwargs:
                record["kwargs"] = {
                    k: _serialize_arg(v) for k, v in kwargs.items()
                }

            line = json.dumps(record, default=str) + "\n"

            with self._write_lock:
                with open(self._file_path, "a", encoding="utf-8") as f:
                    f.write(line)
        except Exception:
            logger.exception("Failed to write trace request: %s", method)
