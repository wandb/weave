import io
import sys

import pytest

import weave
from weave.trace.constants import TRACE_CALL_EMOJI


@weave.op
def func():
    return 1


@weave.op
async def afunc():
    return 2


def test_call_prints_link(client):
    captured_stdout = io.StringIO()
    sys.stdout = captured_stdout

    func()
    output = captured_stdout.getvalue()
    assert TRACE_CALL_EMOJI in output


@pytest.mark.asyncio
async def test_async_call_prints_link(client):
    captured_stdout = io.StringIO()
    sys.stdout = captured_stdout

    await afunc()
    output = captured_stdout.getvalue()
    assert TRACE_CALL_EMOJI in output
