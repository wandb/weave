from __future__ import annotations

import logging
import os
import threading
import time
from typing import Any

from httpx import HTTPError
from pydantic import ValidationError

from weave.trace.sampling import (
    SamplingDecision,
    decide_project_sampling,
)
from weave.trace_server import trace_server_interface as tsi
from weave.trace_server_bindings.client_interface import TraceServerClientInterface

logger = logging.getLogger(__name__)

DEFAULT_SAMPLING_REFRESH_SECONDS = 300.0
DEFAULT_SAMPLING_FETCH_TIMEOUT_MS = 250.0
STALE_ON_FAILURE_SECONDS = 30.0


class SamplingClient:
    def __init__(
        self,
        server: TraceServerClientInterface,
        project_id: str,
    ) -> None:
        self._server = server
        self._project_id = project_id
        self._snapshot: tsi.SamplingRulesSnapshotRes | None = None
        self._last_success_monotonic: float | None = None
        self._started = False
        self._stop_event = threading.Event()
        self._first_refresh_complete = threading.Event()
        self._lock = threading.Lock()
        self._thread: threading.Thread | None = None
        self._fail_open_reasons_logged: set[str] = set()
        self._refresh_generation = 0

    def start(self) -> None:
        if self._started:
            return
        self._started = True
        self._thread = threading.Thread(
            target=self._refresh_loop,
            name="weave-sampling-refresh",
            daemon=True,
        )
        self._thread.start()

    def close(self) -> None:
        self._stop_event.set()

    def decide_root(
        self,
        *,
        trace_id: str,
        op_name: str,
        attributes: dict[str, Any] | None,
    ) -> SamplingDecision:
        self.start()
        self._first_refresh_complete.wait(_fetch_timeout_seconds())
        snapshot = self._get_snapshot()
        return decide_project_sampling(
            snapshot,
            trace_id=trace_id,
            op_name=op_name,
            attributes=attributes,
        )

    def _get_snapshot(self) -> tsi.SamplingRulesSnapshotRes | None:
        with self._lock:
            snapshot = self._snapshot
            last_success = self._last_success_monotonic
        if snapshot is None or last_success is None:
            return None
        stale_deadline = _refresh_seconds() + STALE_ON_FAILURE_SECONDS
        if time.monotonic() - last_success > stale_deadline:
            self._log_fail_open_once("snapshot_stale")
            return None
        return snapshot

    def _refresh_loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                self._refresh_once()
            except (
                NotImplementedError,
                HTTPError,
                OSError,
                TimeoutError,
                ValidationError,
                ValueError,
            ):
                self._log_fail_open_once("snapshot_fetch_error")
                logger.debug("Failed to refresh Weave sampling rules", exc_info=True)
            finally:
                self._first_refresh_complete.set()
            self._stop_event.wait(_refresh_seconds())

    def _refresh_once(self) -> None:
        with self._lock:
            self._refresh_generation += 1
            refresh_generation = self._refresh_generation
        snapshot = self._server.sampling_rules_read(
            tsi.SamplingRulesReadReq(project_id=self._project_id, consumer="sdk")
        )
        if not _snapshot_is_supported(snapshot):
            self._log_fail_open_once("hash_unsupported")
            with self._lock:
                if refresh_generation != self._refresh_generation:
                    return
                self._snapshot = None
                self._last_success_monotonic = None
            return
        with self._lock:
            if refresh_generation != self._refresh_generation:
                return
            self._snapshot = snapshot
            self._last_success_monotonic = time.monotonic()

    def _log_fail_open_once(self, reason: str) -> None:
        if reason in self._fail_open_reasons_logged:
            return
        self._fail_open_reasons_logged.add(reason)
        logger.warning("Weave sampling fail-open: %s", reason)


def _snapshot_is_supported(snapshot: tsi.SamplingRulesSnapshotRes) -> bool:
    try:
        return (
            snapshot.schema_version == 1
            and snapshot.hash.algorithm == "xxh64"
            and snapshot.hash.seed == 0
        )
    except AttributeError:
        return False


def _refresh_seconds() -> float:
    raw = os.getenv("WEAVE_SAMPLING_REFRESH_S")
    if raw is None:
        return DEFAULT_SAMPLING_REFRESH_SECONDS
    try:
        return max(float(raw), 1.0)
    except ValueError:
        logger.warning(
            "Invalid WEAVE_SAMPLING_REFRESH_S=%r; using default %s",
            raw,
            DEFAULT_SAMPLING_REFRESH_SECONDS,
        )
        return DEFAULT_SAMPLING_REFRESH_SECONDS


def _fetch_timeout_seconds() -> float:
    raw = os.getenv("WEAVE_SAMPLING_FETCH_TIMEOUT_MS")
    if raw is None:
        return DEFAULT_SAMPLING_FETCH_TIMEOUT_MS / 1000.0
    try:
        return max(float(raw), 0.0) / 1000.0
    except ValueError:
        logger.warning(
            "Invalid WEAVE_SAMPLING_FETCH_TIMEOUT_MS=%r; using default %s",
            raw,
            DEFAULT_SAMPLING_FETCH_TIMEOUT_MS,
        )
        return DEFAULT_SAMPLING_FETCH_TIMEOUT_MS / 1000.0
