from typing import Callable, Generic, List, TypeVar
from threading import Thread, Lock, Event
from queue import Queue
import time
import atexit

T = TypeVar('T')

class AsyncBatchProcessor(Generic[T]):
    def __init__(self, processor_fn: Callable[[List[T]], None], max_batch_size: int = 100, min_batch_interval: float = 1.0) -> None:
        self.processor_fn = processor_fn
        self.max_batch_size = max_batch_size
        self.min_batch_interval = min_batch_interval
        self.queue: Queue[T] = Queue()
        self.lock = Lock()
        self.stop_event = Event()  # Use an event to signal stopping
        self.processing_thread = Thread(target=self._process_batches)
        self.processing_thread.daemon = True
        self.processing_thread.start()
        atexit.register(self.wait_until_all_processed)  # Register cleanup function

    def enqueue(self, items: List[T]) -> None:
        with self.lock:
            for item in items:
                self.queue.put(item)

    def _process_batches(self) -> None:
        while True:
            current_batch: List[T] = []
            while not self.queue.empty() and len(current_batch) < self.max_batch_size:
                current_batch.append(self.queue.get())

            if current_batch:
                self.processor_fn(current_batch)

            if self.stop_event.is_set() and self.queue.empty():
                break
            
            # Unless we are stopping, sleep for a the min_batch_interval
            if not self.stop_event.is_set():
                time.sleep(self.min_batch_interval)

    def wait_until_all_processed(self) -> None:
        self.stop_event.set()
        self.processing_thread.join()


