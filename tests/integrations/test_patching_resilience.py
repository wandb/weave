import pytest
from weave.integrations.patcher import MultiPatcher, SymbolPatcher
from tests.trace.util import DummyTestException
from typing import Callable

from weave.trace.context import call_context

def assert_no_current_call():
    assert call_context.get_current_call() is None


@pytest.mark.disable_logging_error_check
def test_resilience_to_patcher_errors(client, log_collector):
    class Module:
        def method(self):
            return 0

    def custom_patcher(m: Callable):
        raise DummyTestException("FAILURE!")

    def do_test():
        test_patcher = MultiPatcher(
            [
                SymbolPatcher(
                    lambda: Module,
                    "method",
                    custom_patcher,
                )
            ]
        )

        test_patcher.attempt_patch()

        return Module().method()

    res = do_test()
    assert res == 0

    assert_no_current_call()

    logs = log_collector.get_error_logs()
    assert len(logs) == 1
    assert logs[0].msg.startswith("Failed to patch")
