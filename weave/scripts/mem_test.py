# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "weave @ /Users/timothysweeney/Workspace/github/wandb/core/services/weave-python/weave-public",
#     "pillow",
#     "pympler",
#     "objgraph"
# ]
# ///

import time

import weave

start_time = time.time()

import random

import psutil
from PIL import Image
from psutil._common import bytes2human


class MemoryRecorder:
    """Records and tracks memory usage of the current process."""

    def __init__(self):
        """Initialize the memory recorder with baseline measurements."""
        self.process = psutil.Process()
        self.initial_memory = self.process.memory_info().rss
        self.last_memory = self.initial_memory

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
            "current_usage": bytes2human(current_memory),
            "delta": bytes2human(delta),
            "total_change": bytes2human(total_change),
            "total_change_detailed": total_change
        }

        self.last_memory = current_memory
        return stats

# import objgraph


# gc.set_debug(gc.DEBUG_STATS)
# import weave

# print(weave)
# client = weave.init("mem-test")
memory_recorder = MemoryRecorder()

img_data = [(random.randint(0, 255), random.randint(0, 255), random.randint(0, 255)) for _ in range(2000 * 2000)]

@weave.op
def generate_random_image(width: int, height: int) -> Image:
    # image = Image.new("RGB", (width, height), "red")
    # image.putdata(img_data)
    # image = image.crop((0, 0, width, height))
    # time.sleep(1)
    # with NamedTemporaryFile(suffix=".png") as f:
    #     image.save(f.name)
    #     image = Image.open(f.name)
    return None

# # @weave.op
# def simple_return(x: int) -> int:
#     return [x for _ in range(100000)]

# @profile
# tr = tracker.SummaryTracker()
def main(count: int) -> None:
    # tr.print_diff()
    print("Start", time.time() - start_time)
    res = []

    for i in range(count):
        # tr.print_diff()
        # image = generate_random_image(2000, 2000)
        data = [(random.randint(0, 255), random.randint(0, 255), random.randint(0, 255)) for _ in range(2000 * 2000)]
        print(f"B_{i}_before_image", memory_recorder.get_delta_stats())
        image = Image.new("RGB", (2000, 2000), "red")
        image.putdata(data)
        print(f"B_{i}_after_image", memory_recorder.get_delta_stats())
        del image
        del data
        # client._flush()
        print(f"B_{i}_post_flush", memory_recorder.get_delta_stats())
        # gc.collect()
        print(f"B_{i}_post_gc", memory_recorder.get_delta_stats())
        # generate_random_image.ref = None
        # gc.collect()
        # print(f"B_{i}_post_drop", memory_recorder.get_delta_stats())

        # res.append(image)
        # objgraph.show_growth()
        # simple_return(i)
        print(f"Generated image {i}")


    return res


if __name__ == "__main__":

    # tr.print_diff()
    # objgraph.show_growth()
    print("A", memory_recorder.get_delta_stats())
    main(10)
    print("C", memory_recorder.get_delta_stats())
    # objgraph.show_growth()
    # tr.print_diff()
    print("done")
