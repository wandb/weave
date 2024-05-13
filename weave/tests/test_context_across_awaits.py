import contextvars
import copy
import asyncio
import pytest


def setup():
    stack: contextvars.ContextVar[list[str]] = contextvars.ContextVar(
        "test_context_across_awaits_stack", default=[]
    )

    def print_stack():
        print(stack.get())

    def push_stack(val: str):
        print("start: push_stack", val)
        print_stack()
        new_stack = copy.copy(stack.get())
        new_stack.append(val)
        stack.set(new_stack)
        print("end: push_stack", val)
        print_stack()

    def pop_stack():
        print("start: pop_stack")
        print_stack()
        new_stack = copy.copy(stack.get())
        new_stack.pop()
        stack.set(new_stack)
        print("end: pop_stack")
        print_stack()

    def sync_fn():
        push_stack("non_async")
        pop_stack()

    async def async_fn():
        push_stack("async_fn")
        pop_stack()

    # asyncio.run(async_fn_inside_sync())
    # inside -> copy the stack and run the coroutine.
    # outside -> reset the context to what it was at time of calling.

    def async_fn_inside_sync():
        push_stack("async_fn_inside_sync")  # -> stack is pushed

        async def inner_async_fn():
            push_stack("inner_async_fn")
            await async_fn()
            pop_stack()
            # Purposely putting the second pop inside
            pop_stack()

        return inner_async_fn()  # -> returns a coroutine object

    async def sync_fn_inside_async():
        push_stack("sync_fn_inside_async")

        def inner_sync_fn():
            push_stack("inner_sync_fn")
            pop_stack()
            # Purposely putting the second pop inside
            pop_stack()

        await async_fn()
        inner_sync_fn()

    return (stack, sync_fn, async_fn, async_fn_inside_sync, sync_fn_inside_async)


def test_context_across_awaits():
    (stack, sync_fn, async_fn, async_fn_inside_sync, sync_fn_inside_async) = setup()
    assert stack.get() == []
    sync_fn()
    assert stack.get() == []
    asyncio.run(async_fn())
    assert stack.get() == []
    asyncio.run(async_fn_inside_sync())
    assert stack.get() == []
    asyncio.run(sync_fn_inside_async())
    assert stack.get() == []


@pytest.mark.asyncio
async def test_context_across_awaits_async():
    (stack, sync_fn, async_fn, async_fn_inside_sync, sync_fn_inside_async) = setup()
    assert stack.get() == []
    sync_fn()
    assert stack.get() == []
    await async_fn()
    assert stack.get() == []
    await async_fn_inside_sync()
    assert stack.get() == []
    await sync_fn_inside_async()
    assert stack.get() == []
