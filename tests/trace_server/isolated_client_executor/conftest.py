"""Conftest for isolated_client_executor tests.

On non-Windows platforms, patches the executor to use fork instead of spawn.
Fork copies parent memory instantly (~0.01s) vs spawn re-importing weave (~5s),
cutting total test time from ~90s to ~5s.
"""

import multiprocessing
import sys

import pytest

from weave.trace.context.weave_client_context import set_weave_client_global
from weave.trace_server.isolated_client_executor import (
    IsolatedClientExecutor,
    _worker_loop,
)

# fork is unavailable on Windows
USE_FORK = sys.platform != "win32"


def _fork_worker_loop(*args, **kwargs):
    """Clear inherited client state from fork, then run the real worker loop."""
    set_weave_client_global(None)
    return _worker_loop(*args, **kwargs)


def _fork_ensure_process_running(self):
    """Replacement for _ensure_process_running that uses fork context."""
    if self.is_running:
        return

    ctx = multiprocessing.get_context("fork")
    self._request_queue = ctx.Queue()
    self._response_queue = ctx.Queue()

    self._process = ctx.Process(
        target=_fork_worker_loop,
        args=(
            self.client_factory,
            self.client_factory_config,
            self._request_queue,
            self._response_queue,
        ),
    )
    self._process.start()


if USE_FORK:

    @pytest.fixture(autouse=True)
    def _use_fork_for_executor(monkeypatch):
        """Patch IsolatedClientExecutor to use fork instead of spawn."""
        monkeypatch.setattr(
            IsolatedClientExecutor,
            "_ensure_process_running",
            _fork_ensure_process_running,
        )
