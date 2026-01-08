"""Single-thread scheduler for delayed execution using sched."""

import sched
import threading
import time
from collections.abc import Callable


class DelayedScheduler:
    """Schedules callbacks to run after a delay using a single background thread."""

    def __init__(self) -> None:
        self._scheduler = sched.scheduler(time.monotonic, time.sleep)
        self._shutdown = False
        self._thread = threading.Thread(
            target=self._run, daemon=True, name="weave-delayed-scheduler"
        )
        self._thread.start()

    def schedule(
        self, delay_seconds: float, callback: Callable[[], None]
    ) -> sched.Event:
        """Schedule callback to run after delay_seconds. Returns event for cancellation."""
        return self._scheduler.enter(delay_seconds, 1, callback)

    def cancel(self, event: sched.Event) -> None:
        """Cancel a scheduled event."""
        try:
            self._scheduler.cancel(event)
        except ValueError:
            pass  # Already executed or cancelled

    def _run(self) -> None:
        while not self._shutdown:
            self._scheduler.run(blocking=False)
            time.sleep(0.01)  # Poll interval

    def shutdown(self) -> None:
        self._shutdown = True
        self._thread.join(timeout=5.0)
