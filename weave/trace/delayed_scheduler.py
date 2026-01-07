"""Single-thread scheduler for delayed execution using a min-heap."""

import heapq
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field


@dataclass(order=True)
class ScheduledTask:
    deadline: float
    callback: Callable[[], None] = field(compare=False)
    cancelled: bool = field(default=False, compare=False)


class DelayedScheduler:
    """Schedules callbacks to run after a delay using a single background thread."""

    def __init__(self) -> None:
        self._heap: list[ScheduledTask] = []
        self._lock = threading.Lock()
        self._condition = threading.Condition(self._lock)
        self._shutdown = False
        self._thread = threading.Thread(
            target=self._run, daemon=True, name="weave-delayed-scheduler"
        )
        self._thread.start()

    def schedule(
        self, delay_seconds: float, callback: Callable[[], None]
    ) -> ScheduledTask:
        """Schedule callback to run after delay_seconds. Returns task for cancellation."""
        task = ScheduledTask(
            deadline=time.monotonic() + delay_seconds,
            callback=callback,
        )
        with self._condition:
            heapq.heappush(self._heap, task)
            self._condition.notify()
        return task

    def cancel(self, task: ScheduledTask) -> None:
        """Mark task as cancelled. It will be skipped when its deadline arrives."""
        task.cancelled = True

    def _run(self) -> None:
        while True:
            with self._condition:
                # Wait for tasks or shutdown
                while not self._heap and not self._shutdown:
                    self._condition.wait()

                if self._shutdown:
                    return

                # Wait until next deadline
                wait_time = self._heap[0].deadline - time.monotonic()
                if wait_time > 0:
                    self._condition.wait(timeout=wait_time)
                    continue

                task = heapq.heappop(self._heap)

            # Execute outside lock
            if not task.cancelled:
                try:
                    task.callback()
                except Exception:
                    pass

    def shutdown(self) -> None:
        with self._condition:
            self._shutdown = True
            self._condition.notify()
        self._thread.join(timeout=5.0)
