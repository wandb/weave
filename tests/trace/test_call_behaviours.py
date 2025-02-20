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
