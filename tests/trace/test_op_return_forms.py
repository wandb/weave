import pytest

import weave
from weave.trace.ref_util import get_ref
from weave.trace_server import trace_server_interface as tsi


@pytest.mark.parametrize("expected_output", [None, 1])
def test_op_return_sync_value(client, expected_output):
    # Ops return literals (no closure) to exercise the global-var resolution
    # branch in op serialization.
    if expected_output is None:

        @weave.op
        def fn():
            return
    else:

        @weave.op
        def fn():
            return 1

    fn()

    res = client.server.calls_query(
        tsi.CallsQueryReq(
            project_id=client.project_id,
        )
    )

    obj_ref = get_ref(fn)
    assert obj_ref is not None
    assert res.calls[0].op_name == obj_ref.uri
    assert res.calls[0].inputs == {}
    assert res.calls[0].output == expected_output


@pytest.mark.asyncio
@pytest.mark.parametrize("expected_output", [None, 1])
async def test_op_return_async_value(client, expected_output):
    if expected_output is None:

        @weave.op
        async def fn():
            return
    else:

        @weave.op
        async def fn():
            return 1

    await fn()

    res = client.server.calls_query(
        tsi.CallsQueryReq(
            project_id=client.project_id,
        )
    )

    obj_ref = get_ref(fn)
    assert obj_ref is not None
    assert res.calls[0].op_name == obj_ref.uri
    assert res.calls[0].inputs == {}
    assert res.calls[0].output == expected_output


""" The streaming tests below are permutations of:
    - (2x) sync/async
    - (2x) generator/iterator
    - (4x) never iterated/fully iterated/partially iterated/exception thrown
"""

FULLY = list(range(9, -1, -1))
PARTIAL = list(range(9, 4, -1))


@pytest.mark.parametrize(
    ("consume", "expected_output", "expect_exception"),
    [
        ("never", None, False),
        ("full", FULLY, False),
        ("partial", PARTIAL, False),
        ("exception", PARTIAL, True),
    ],
)
def test_op_return_sync_generator(client, consume, expected_output, expect_exception):
    # Distinct closure-free op bodies so op serialization sees no free vars.
    if expect_exception:

        @weave.op(accumulator=simple_list_accumulator)
        def fn():
            size = 10
            while size > 0:
                size -= 1
                yield size
                if size == 5:
                    raise ValueError("test")
    else:

        @weave.op(accumulator=simple_list_accumulator)
        def fn():
            size = 10
            while size > 0:
                size -= 1
                yield size

    if consume == "never":
        fn()
    elif consume == "full":
        for _item in fn():
            pass
    elif consume == "partial":
        for item in fn():
            if item == 5:
                break
    elif consume == "exception":
        try:
            for _item in fn():
                pass
        except ValueError:
            pass
    else:
        raise AssertionError(f"unknown consume mode: {consume}")

    res = client.server.calls_query(
        tsi.CallsQueryReq(
            project_id=client.project_id,
        )
    )

    obj_ref = get_ref(fn)
    assert obj_ref is not None
    assert res.calls[0].op_name == obj_ref.uri
    assert res.calls[0].inputs == {}
    assert res.calls[0].output == expected_output
    if expect_exception:
        assert res.calls[0].exception is not None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("consume", "expected_output", "expect_exception"),
    [
        ("never", None, False),
        ("full", FULLY, False),
        ("partial", PARTIAL, False),
        ("exception", PARTIAL, True),
    ],
)
async def test_op_return_async_generator(
    client, consume, expected_output, expect_exception
):
    if expect_exception:

        @weave.op(accumulator=simple_list_accumulator)
        async def fn():
            size = 10
            while size > 0:
                size -= 1
                yield size
                if size == 5:
                    raise ValueError("test")
    else:

        @weave.op(accumulator=simple_list_accumulator)
        async def fn():
            size = 10
            while size > 0:
                size -= 1
                yield size

    if consume == "never":
        async for _item in fn():
            return  # `return` raises StopAsyncIteration to close the op
    elif consume == "full":
        async for _item in fn():
            pass
    elif consume == "partial":
        async for item in fn():
            if item == 5:
                break
            return  # required to raise StopAsyncIteration
    elif consume == "exception":
        try:
            async for _item in fn():
                pass
        except ValueError:
            pass
    else:
        raise AssertionError(f"unknown consume mode: {consume}")

    res = client.server.calls_query(
        tsi.CallsQueryReq(
            project_id=client.project_id,
        )
    )

    obj_ref = get_ref(fn)
    assert obj_ref is not None
    assert res.calls[0].op_name == obj_ref.uri
    assert res.calls[0].inputs == {}
    assert res.calls[0].output == expected_output
    if expect_exception:
        assert res.calls[0].exception is not None


@pytest.mark.parametrize(
    ("consume", "expected_output", "expect_exception"),
    [
        ("never", None, False),
        ("full", FULLY, False),
        ("partial", PARTIAL, False),
        ("exception", PARTIAL, True),
    ],
)
def test_op_return_sync_iterator(client, consume, expected_output, expect_exception):
    class MyIterator:
        size = 10

        def __iter__(self):
            return self

        def __next__(self):
            if self.size == 0:
                raise StopIteration
            if expect_exception and self.size == 5:
                raise ValueError("test")
            self.size -= 1
            return self.size

    @weave.op(accumulator=simple_list_accumulator)
    def fn():
        return MyIterator()

    if consume == "never":
        fn()
    elif consume == "full":
        for _item in fn():
            pass
    elif consume == "partial":
        for item in fn():
            if item == 5:
                break
    elif consume == "exception":
        try:
            for _item in fn():
                pass
        except ValueError:
            pass
    else:
        raise AssertionError(f"unknown consume mode: {consume}")

    res = client.server.calls_query(
        tsi.CallsQueryReq(
            project_id=client.project_id,
        )
    )

    obj_ref = get_ref(fn)
    assert obj_ref is not None
    assert res.calls[0].op_name == obj_ref.uri
    assert res.calls[0].inputs == {}
    assert res.calls[0].output == expected_output
    if expect_exception:
        assert res.calls[0].exception is not None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("consume", "expected_output", "expect_exception"),
    [
        ("never", None, False),
        ("full", FULLY, False),
        ("partial", PARTIAL, False),
        ("exception", PARTIAL, True),
    ],
)
async def test_op_return_async_iterator(
    client, consume, expected_output, expect_exception
):
    class MyAsyncIterator:
        size = 10

        def __aiter__(self):
            return self

        async def __anext__(self):
            if self.size == 0:
                raise StopAsyncIteration
            if expect_exception and self.size == 5:
                raise ValueError("test")
            self.size -= 1
            return self.size

    @weave.op(accumulator=simple_list_accumulator)
    def fn():
        return MyAsyncIterator()

    if consume == "never":
        fn()
    elif consume == "full":
        async for _item in fn():
            pass
    elif consume == "partial":
        async for item in fn():
            if item == 5:
                break
    elif consume == "exception":
        try:
            async for _item in fn():
                pass
        except ValueError:
            pass
    else:
        raise AssertionError(f"unknown consume mode: {consume}")

    res = client.server.calls_query(
        tsi.CallsQueryReq(
            project_id=client.project_id,
        )
    )

    obj_ref = get_ref(fn)
    assert obj_ref is not None
    assert res.calls[0].op_name == obj_ref.uri
    assert res.calls[0].inputs == {}
    assert res.calls[0].output == expected_output
    if expect_exception:
        assert res.calls[0].exception is not None


def simple_list_accumulator(acc, value):
    if acc is None:
        acc = []
    acc.append(value)
    return acc
