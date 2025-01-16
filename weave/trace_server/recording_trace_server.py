

import threading
import time
from collections import defaultdict
from datetime import datetime
from functools import wraps
from typing import Optional, TypedDict

from weave.trace_server.trace_server_interface import TraceServerInterface


class LogRecord(TypedDict):
    timestamp: datetime
    name: str
    duration: float
    error: Optional[str]

class RecordingTraceServer(TraceServerInterface):
    _next_ts: TraceServerInterface
    _log: list[LogRecord]

    def __init__(self, next_ts: TraceServerInterface):
        self._next_ts = next_ts
        self._log: list[LogRecord] = []
        self._log_lock = threading.Lock()

    def __getattribute__(self, name):
        protected_names = ["_next_ts", "_log", "_log_lock", "_thread_safe_log", "get_log", "summarize_logs", "reset_log"]
        if name in protected_names:
            return super().__getattribute__(name)
        attr = self._next_ts.__getattribute__(name)

        if name.startswith("_") or not callable(attr):
            return attr

        @wraps(attr)
        def wrapper(*args, **kwargs):
            now = datetime.now()
            start = time.perf_counter()
            try:
                if name == "file_create":
                    print(args[0].name)
                res = attr(*args, **kwargs)
                end = time.perf_counter()
                self._thread_safe_log(LogRecord(timestamp=now, name=name, duration=end - start))
            except Exception as e:
                end = time.perf_counter()
                self._thread_safe_log(LogRecord(timestamp=now, name=name, duration=end - start, error=str(e)))
                raise e
            return res

        return wrapper

    def _thread_safe_log(self, log: LogRecord):
        with self._log_lock:
            self._log.append(log)

    def get_log(self) -> list[LogRecord]:
        # if isinstance(self._next_ts, RecordingTraceServer):
        #     next_log = self._next_ts.get_log()
        # else:
        #     next_log = {}
        return self._log
        # return {
        #     "name": self._name,
        #     "log": self._log,
        #     # "next": next_log,
        # }

    def reset_log(self):
        with self._log_lock:
            self._log = []

    def summarize_logs(self) -> dict:
        log_groups = defaultdict(list)
        for log in self._log:
            log_groups[log["name"]].append(log)
        groups = {}
        for name, logs in log_groups.items():
            total_duration = sum(log["duration"] for log in logs)
            count = len(logs)
            error_count =    sum(1 for log in logs if log["error"] is not None)
            groups[name] = {
                "total_duration": total_duration,
                "count": count,
                "average_duration": total_duration / count,
                "error_count": error_count,
            }
        return groups
