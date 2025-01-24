# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "weave @ ..",
# ]
# ///

import gc
import time

import psutil

import weave


class MemoryRecorder:
    """Records and tracks memory usage of the current process."""

    def __init__(self):
        """Initialize the memory recorder with baseline measurements."""
        self.process = psutil.Process()
        self.initial_memory = self.process.memory_info().rss
        self.last_memory = self.initial_memory
        self.start_time = time.time()

    def get_delta_stats(self) -> dict:
        """Get the current memory usage statistics as a dictionary.
        
        Returns:
            dict: Contains current memory usage, delta since last check, and total change
                 since initialization, all in bytes.
        """
        current_memory = self.process.memory_info().rss
        delta = current_memory - self.last_memory
        total_change = current_memory - self.initial_memory

        stats = {
            "current_usage": current_memory,
            "delta": delta,
            "total_change": total_change,
        }

        self.last_memory = current_memory
        return stats

    def print_stats(self, label: str = "") -> None:
        """Print memory statistics with aligned numbers.
        
        Args:
            label: Optional label to prefix the stats output
        """
        stats = self.get_delta_stats()
        timestamp = f"{time.time() - self.start_time:.2f}s"
        print(f"[{timestamp}] {label:20} Delta: {stats['delta']:>15} "
              f"Total Change: {stats['total_change']:>15} "
              f"Current: {stats['current_usage']:>15}")

print(weave)
# client = weave.init("mem-test-2")
import pydantic


class LargeReturnObject(weave.Object):
    model_config = pydantic.ConfigDict(arbitrary_types_allowed=True)
    data: bytearray

    @classmethod
    def of_size(cls, bytes: int) -> "LargeReturnObject":
        # Use bytearray which allocates exact bytes and is garbage collected properly
        data = bytearray(bytes)
        return cls(data=data)

@weave.op
def create_large_return_object(bytes: int) -> LargeReturnObject:
    return LargeReturnObject.of_size(bytes)

time.sleep(1)
memory_recorder = MemoryRecorder()
def main(count: int, bytes: int) -> None:
    memory_recorder.print_stats("Main Entry")
    res = []
    for i in range(count):
        memory_recorder.print_stats(f"Before {i}")
        res.append(create_large_return_object(bytes))
        memory_recorder.print_stats(f"After {i}")

        # Print object reference count before deletion
        # print(f"Reference count for res: {sys.getrefcount(res)}")

        # client._flush()
        gc.collect(generation=2)
        memory_recorder.print_stats(f"After flush / gc {i}")

        # del res
        gc.collect(generation=2)
        memory_recorder.print_stats(f"After del / gc {i}")

        # print("Uncollectable objects:", gc.get_count())
        # print("Garbage objects:", len(gc.garbage))

        # time.sleep(1)
        # memory_recorder.print_stats(f"After sleep {i}")

    memory_recorder.print_stats("Main Exit")


if __name__ == "__main__":
    main(10, 2_000_000_000)
