import io
import sys
import time
from collections import Counter

import pytest

import weave
from weave.trace.constants import TRACE_CALL_EMOJI


@weave.op
def func():
    return 1


@weave.op
async def afunc():
    return 2


def _capture_output(fn, client):
    captured_stdout = io.StringIO()
    sys.stdout = captured_stdout

    try:
        fn()
    except:
        pass

    client.future_executor.flush()
    time.sleep(0.01)  # Ensure on_finish_callback has time to fire post-flush

    return Counter(captured_stdout.getvalue())


async def _capture_output_async(fn, client):
    captured_stdout = io.StringIO()
    sys.stdout = captured_stdout

    try:
        await fn()
    except:
        pass

    client.future_executor.flush()
    time.sleep(0.01)  # Ensure on_finish_callback has time to fire post-flush

    return Counter(captured_stdout.getvalue())


def test_call_prints_link(client):
    c = _capture_output(func, client)
    assert c[TRACE_CALL_EMOJI] == 1


@pytest.mark.disable_logging_error_check
def test_call_doesnt_print_link_if_failed(client_with_throwing_server):
    c = _capture_output(func, client_with_throwing_server)
    assert c[TRACE_CALL_EMOJI] == 0


@pytest.mark.asyncio
async def test_async_call_prints_link(client):
    c = await _capture_output_async(afunc, client)
    assert c[TRACE_CALL_EMOJI] == 1


@pytest.mark.disable_logging_error_check
@pytest.mark.asyncio
async def test_async_call_doesnt_print_link_if_failed(client_with_throwing_server):
    c = await _capture_output_async(afunc, client_with_throwing_server)
    assert c[TRACE_CALL_EMOJI] == 0
