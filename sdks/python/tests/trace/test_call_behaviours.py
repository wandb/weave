import io
import sys
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


def test_call_prints_link(client):
    captured_stdout = io.StringIO()
    sys.stdout = captured_stdout

    func()
    output = captured_stdout.getvalue()
    c = Counter(output)
    assert c[TRACE_CALL_EMOJI] == 1


@pytest.mark.asyncio
async def test_async_call_prints_link(client):
    captured_stdout = io.StringIO()
    sys.stdout = captured_stdout

    await afunc()
    output = captured_stdout.getvalue()
    c = Counter(output)
    assert c[TRACE_CALL_EMOJI] == 1
