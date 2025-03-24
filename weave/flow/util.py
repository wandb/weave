import asyncio
import logging
import multiprocessing
import random
from collections import defaultdict
from collections.abc import AsyncIterator, Awaitable, Iterable
from typing import Any, Callable, TypeVar

T = TypeVar("T")
U = TypeVar("U")

_shown_warnings = set()


def transpose(rows: list[dict]) -> dict[str, list]:
    cols = defaultdict(list)
    for row in rows:
        for k, v in row.items():
            cols[k].append(v)
    return dict(cols)


async def async_foreach(
    sequence: Iterable[T],
    func: Callable[[T], Awaitable[U]],
    max_concurrent_tasks: int,
) -> AsyncIterator[tuple[T, U]]:
    """Process items from a sequence concurrently with a maximum number of parallel tasks.

    This function loads items from the input sequence lazily to support large or infinite
    sequences. Items are processed and yielded in the same order as the input sequence.

    Args:
        sequence: An iterable of items to process. Items are loaded lazily.
        func: An async function that processes each item from the sequence.
        max_concurrent_tasks: Maximum number of items to process concurrently.

    Yields:
        Tuples of (original_item, processed_result) in the same order as the input sequence.

    Example:
        ```python
        async def process(x: int) -> str:
            await asyncio.sleep(1)  # Simulate async work
            return str(x * 2)

        async for item, result in async_foreach(range(10), process, max_concurrent_tasks=3):
            print(f"Processed {item} -> {result}")
        ```

    Notes:
        - If func raises an exception, it will be propagated to the caller
        - Memory usage is bounded by max_concurrent_tasks
        - All pending tasks are properly cleaned up on error or cancellation
        - Results are yielded in the same order as the input sequence
    """
    semaphore = asyncio.Semaphore(max_concurrent_tasks)
    active_tasks: list[asyncio.Task] = []

    async def process_item(item: T) -> tuple[T, U]:
        """Process a single item using the provided function with semaphore control."""
        async with semaphore:
            result = await func(item)
            return item, result

    def maybe_queue_next_task() -> None:
        """Attempt to queue the next task from the iterator if available."""
        try:
            item = next(iterator)
            task = asyncio.create_task(process_item(item))
            active_tasks.append(task)
        except StopIteration:
            pass

    iterator = iter(sequence)

    try:
        # Prime the initial set of tasks
        for _ in range(max_concurrent_tasks):
            maybe_queue_next_task()

        while active_tasks:
            # Always wait for the first task in the list to complete
            # This ensures we yield results in order
            task = active_tasks.pop(0)  # Remove completed task from front of list
            try:
                item, result = await task
                yield item, result

                # Add a new task if there are more items
                maybe_queue_next_task()
            except Exception:
                # Clean up remaining tasks before re-raising
                for t in active_tasks:
                    t.cancel()
                await asyncio.gather(*active_tasks, return_exceptions=True)
                raise

    except asyncio.CancelledError:
        # Clean up tasks if the caller cancels this coroutine
        for task in active_tasks:
            task.cancel()
        await asyncio.gather(*active_tasks, return_exceptions=True)
        raise


def _subproc(
    queue: multiprocessing.Queue, func: Callable, *args: Any, **kwargs: Any
) -> None:
    result = func(*args, **kwargs)
    queue.put(result)


def _run_in_process(
    func: Callable, args: tuple = (), kwargs: dict = {}
) -> tuple[multiprocessing.Process, multiprocessing.Queue]:
    """Run a function in a separate process and return the process object and a multiprocessing.Queue for the result."""
    queue: multiprocessing.Queue = multiprocessing.Queue()
    process: multiprocessing.Process = multiprocessing.Process(
        target=_subproc, args=(queue, func) + args, kwargs=kwargs
    )
    process.start()
    return process, queue


async def run_in_process_with_timeout(
    timeout: float, func: Callable, *args: Any, **kwargs: Any
) -> Any:
    """Run a function in a separate process with a timeout. Terminate the process if it exceeds the timeout."""
    # Note, on osx, multiprocessing uses spawn by default. With span, subprocesses will re-import main,
    # and incur the cost of bootstrapping python and all imports, which for weave is currently about 1.5s.
    # Scripts that use this can call 'multiprocessing.set_start_method("fork")' which is much faster (0.05s)
    # depending on their use case (there are some issues with fork on osx).
    loop = asyncio.get_running_loop()
    process, queue = _run_in_process(func, args, kwargs)

    try:
        # Wait for the process to complete or timeout
        await asyncio.wait_for(loop.run_in_executor(None, process.join), timeout)
    except asyncio.TimeoutError:
        print("Function execution exceeded the timeout. Terminating process.")
        process.terminate()
        process.join()  # Ensure process resources are cleaned up
        raise

    if process.exitcode == 0:
        return queue.get()  # Retrieve result from the queue
    else:
        raise ValueError(
            "Unhandled exception in subprocess. Exitcode: " + str(process.exitcode)
        )


def warn_once(logger: logging.Logger, message: str) -> None:
    """Display a warning message only once. If the message has already been shown, do nothing."""
    if message not in _shown_warnings:
        logger.warning(message)
        _shown_warnings.add(message)


def make_memorable_name() -> str:
    adjectives = [
        "brave",
        "bright",
        "calm",
        "charming",
        "clever",
        "daring",
        "dazzling",
        "eager",
        "elegant",
        "eloquent",
        "fierce",
        "friendly",
        "gentle",
        "graceful",
        "happy",
        "honest",
        "imaginative",
        "innocent",
        "joyful",
        "jubilant",
        "keen",
        "kind",
        "lively",
        "loyal",
        "merry",
        "nice",
        "noble",
        "optimistic",
        "proud",
        "quiet",
        "rich",
        "sweet",
        "tender",
        "unique",
        "wise",
        "zealous",
    ]

    nouns = [
        "bear",
        "bird",
        "breeze",
        "cedar",
        "cloud",
        "daisy",
        "dawn",
        "dolphin",
        "dusk",
        "eagle",
        "fish",
        "flower",
        "forest",
        "hill",
        "horizon",
        "island",
        "lake",
        "lion",
        "maple",
        "meadow",
        "moon",
        "mountain",
        "oak",
        "ocean",
        "pine",
        "plateau",
        "rain",
        "river",
        "rose",
        "star",
        "stream",
        "sun",
        "tiger",
        "tree",
        "valley",
        "whale",
        "wind",
        "wolf",
    ]

    adj = random.choice(adjectives)
    noun = random.choice(nouns)
    return f"{adj}-{noun}"


def short_str(obj: Any, limit: int = 25) -> str:
    str_val = str(obj)
    if len(str_val) > limit:
        return str_val[:limit] + "..."
    return str_val
