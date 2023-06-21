from concurrent.futures import ThreadPoolExecutor
import contextlib
import contextvars
from typing import Optional, Callable, TypeVar, Iterator, Generator

from . import context
from . import execute
from . import forward_graph
from . import memo
from . import wandb_api

# Must be power of 2
MAX_PARALLELISM = 16
assert MAX_PARALLELISM & (MAX_PARALLELISM - 1) == 0

_parallel_budget_ctx: contextvars.ContextVar[Optional[int]] = contextvars.ContextVar(
    "_parallel_budget_ctx", default=MAX_PARALLELISM
)


def get_parallel_budget() -> int:
    budget = _parallel_budget_ctx.get()
    if budget is None:
        return MAX_PARALLELISM
    return budget


@contextlib.contextmanager
def parallel_budget_ctx(budget: Optional[int]) -> Generator[None, None, None]:
    token = _parallel_budget_ctx.set(budget)
    try:
        yield
    finally:
        _parallel_budget_ctx.reset(token)


ItemType = TypeVar("ItemType")
ResultType = TypeVar("ResultType")


def do_in_parallel(
    do_one: Callable[[ItemType], ResultType], items: list[ItemType]
) -> Iterator[ResultType]:
    parallel_budget = get_parallel_budget()

    if parallel_budget <= 1:
        return map(do_one, items)

    # Contexts aren't automatically propagated to threads, so we have to do so manually for every context
    memo_ctx = memo._memo_storage.get()
    remaining_budget_per_thread = get_remaining_budget_per_thread(len(items))
    wandb_api_ctx = wandb_api.get_wandb_api_context()
    result_store = forward_graph.get_node_result_store()
    top_level_stats = execute.get_top_level_stats()

    def do_one_with_memo_and_parallel_budget(x: ItemType) -> ResultType:
        memo_token = memo._memo_storage.set(memo_ctx)
        thread_result_store = None
        thread_top_level_stats = None
        try:
            with parallel_budget_ctx(remaining_budget_per_thread):
                with wandb_api.wandb_api_context(wandb_api_ctx):
                    with context.execution_client():
                        with forward_graph.node_result_store(
                            result_store
                        ) as thread_result_store:
                            with execute.top_level_stats() as thread_top_level_stats:
                                return do_one(x)
        finally:
            memo._memo_storage.reset(memo_token)
            if thread_result_store is not None:
                result_store.merge(thread_result_store)
            if top_level_stats is not None and thread_top_level_stats is not None:
                top_level_stats.merge(thread_top_level_stats)

    return ThreadPoolExecutor(max_workers=parallel_budget).map(
        do_one_with_memo_and_parallel_budget, items
    )


def get_remaining_budget_per_thread(item_count: int) -> int:
    parallel_budget = get_parallel_budget()
    if item_count <= 0:
        return parallel_budget
    return max(parallel_budget // item_count, 1)
