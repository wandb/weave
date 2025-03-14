import pytest

import weave


@pytest.mark.disable_logging_error_check
def test_generator_with_no_accumulator(client):
    @weave.op
    def inner(x):
        return x + 1

    @weave.op
    def gen():
        for x in range(3):
            yield inner(x)

    res = gen()
    res = list(res)

    calls = list(client.get_calls())
    assert len(calls) == 4

    call = calls[0]
    children = call.children()

    assert len(children) == 3
    for x in range(3):
        assert "inner" in children[x].op_name
        assert children[x].inputs == {"x": x}
        assert children[x].output == x + 1
