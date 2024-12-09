import asyncio
import logging
import multiprocessing
import random
from collections.abc import AsyncIterator, Awaitable, Iterable
from typing import Any, Callable, TypeVar

T = TypeVar("T")
U = TypeVar("U")

_shown_warnings = set()


async def async_foreach(
    sequence: Iterable[T],
    func: Callable[[T], Awaitable[U]],
    max_concurrent_tasks: int,
) -> AsyncIterator[tuple[T, U]]:
    semaphore = asyncio.Semaphore(max_concurrent_tasks)

    async def process_item(item: T) -> tuple[T, U]:
        async with semaphore:
            result = await func(item)
            return item, result

    tasks = [asyncio.create_task(process_item(item)) for item in sequence]

    for task in asyncio.as_completed(tasks):
        item, result = await task
        yield item, result


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
