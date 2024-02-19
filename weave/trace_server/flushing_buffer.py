
# Super cheap way to get buffering - not the best
import threading
import time
import typing

# Super cheap way to get buffering before implementing a proper buffer
# using a queue.
class InMemFlushableBuffer:
    buffer: typing.List
    on_flush: typing.Callable

    def __init__(self, on_flush: typing.Callable):
        # // Does this need to be a queue - probably....
        self.buffer = []
        self.on_flush = on_flush
        self._lock = threading.Lock()

    def insert(self, row: typing.List):
        with self._lock:
            self.buffer.append(row)
    
    def flush(self):
        to_flush = []
        with self._lock:
            to_flush = [*self.buffer]
            self.buffer = []
        self.on_flush(to_flush)


class InMemAutoFlushingBuffer(InMemFlushableBuffer):
    max_buffer_size: int
    max_age_s: int

    def __init__(self, max_buffer_size: int, max_age_s:int, on_flush: typing.Callable):
        super().__init__(on_flush)
        self.max_buffer_size = max_buffer_size
        self.max_age_s = max_age_s

        # Start a background thread to flush the buffer every max_age_s seconds
        # self.queue: queue.Queue = queue.Queue()
        self._thread = threading.Thread(target=self._thread_body)
        self._thread.daemon = True
        self._thread.start()
        # TODO: handle shutdown

    def insert(self, row: typing.List):
        super().insert(row)
        if self.max_buffer_size > 0 and len(self.buffer) >= self.max_buffer_size:
            self.flush()

    def _thread_body(self):
        while True:
            self.flush()
            time.sleep(self.max_age_s)

    def __del__(self):
        self.flush()
