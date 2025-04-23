import pytest

import weave
from tests.trace.util import capture_output, flushing_callback
from weave.trace.constants import TRACE_CALL_EMOJI


@weave.op
def func():
    return 1


@weave.op
async def afunc():
    return 2


def test_call_prints_link(client):
    callbacks = [flushing_callback(client)]
    with capture_output(callbacks) as captured:
        func()

    assert captured.getvalue().count(TRACE_CALL_EMOJI) == 1


@pytest.mark.disable_logging_error_check
def test_call_doesnt_print_link_if_failed(client_with_throwing_server):
    callbacks = [flushing_callback(client_with_throwing_server)]
    with capture_output(callbacks) as captured:
        func()

    assert captured.getvalue().count(TRACE_CALL_EMOJI) == 0


@pytest.mark.asyncio
async def test_async_call_prints_link(client):
    callbacks = [flushing_callback(client)]
    with capture_output(callbacks) as captured:
        await afunc()

    assert captured.getvalue().count(TRACE_CALL_EMOJI) == 1


@pytest.mark.disable_logging_error_check
@pytest.mark.asyncio
async def test_async_call_doesnt_print_link_if_failed(client_with_throwing_server):
    callbacks = [flushing_callback(client_with_throwing_server)]
    with capture_output(callbacks) as captured:
        await afunc()

    assert captured.getvalue().count(TRACE_CALL_EMOJI) == 0


def test_nested_calls_print_single_link(client):
    @weave.op
    def inner(a, b):
        return a + b

    @weave.op
    def middle(a, b):
        return inner(a, b)

    @weave.op
    def outer(a, b):
        return middle(a, b)

    callbacks = [flushing_callback(client)]
    with capture_output(callbacks) as captured:
        outer(1, 2)

    # Check that all 3 calls landed
    calls = list(client.get_calls())
    assert len(calls) == 3

    # But only 1 donut link should be printed
    s = captured.getvalue()
    assert s.count(TRACE_CALL_EMOJI) == 1

    # And that link should be the "outer" call
    s = s.strip("\n")
    _, call_id = s.rsplit("/", 1)

    call = client.get_call(call_id)
    assert "outer" in call.op_name
