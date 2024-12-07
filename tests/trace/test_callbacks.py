import weave
from weave.trace.op_lifecycle import DebugCallback


def test_basic_callback(client, capsys):
    @weave.op(callbacks=[DebugCallback()])
    def generator():
        yield "the "
        yield "quick "
        yield "brown "
        yield "fox"

    for _ in generator():
        pass

    output = capsys.readouterr().out
    assert output.count(">>> before_call_start") == 1
    assert output.count(">>> before_yield") == 4
    assert output.count(">>> after_error") == 0
    assert output.count(">>> before_call_finish") == 1


def test_error_callback(client, capsys):
    @weave.op(callbacks=[DebugCallback()])
    def generator():
        yield "the "
        yield "quick "
        raise Exception("oops")
        yield "brown "
        yield "fox"

    try:
        for _ in generator():
            pass
    except Exception:
        pass

    output = capsys.readouterr().out
    assert output.count(">>> before_call_start") == 1
    assert output.count(">>> before_yield") == 2
    assert output.count(">>> after_error") == 1
    assert output.count(">>> before_call_finish") == 1
