import asyncio
import multiprocessing
from typing import Any, AsyncIterator, Awaitable, Callable, Iterable, Tuple, TypeVar

T = TypeVar("T")
U = TypeVar("U")


async def async_foreach(
    sequence: Iterable[T],
    func: Callable[[T], Awaitable[U]],
    max_concurrent_tasks: int,
) -> AsyncIterator[Tuple[T, U]]:
    semaphore = asyncio.Semaphore(max_concurrent_tasks)

    async def process_item(item: T) -> Tuple[T, U]:
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
    func: Callable, args: Tuple = (), kwargs: dict = {}
) -> Tuple[multiprocessing.Process, multiprocessing.Queue]:
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
