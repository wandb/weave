import weave
from .. import context_state as _context_state


def test_weaveflow_basic_addition(user_by_api_key_in_env):
    with _context_state.eager_execution():
        weave.init("weaveflow_example")

        @weave.op()
        def custom_adder(a: int, b: int) -> int:
            return a + b

        res = custom_adder(1, 2)
        assert res == 3


def test_weaveflow_return_list(user_by_api_key_in_env):
    with _context_state.eager_execution():
        project = "weaveflow_example"
        weave.init(project)

        @weave.op()
        def custom_adder(a: int, b: int) -> list[int]:
            return [a + b]

        res = custom_adder(1, 2)
        assert res == [3]
