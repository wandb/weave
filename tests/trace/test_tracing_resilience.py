"""
The purpose of this test suite is to ensure that Weave can handle various types of errors that can occur during tracing.

We should never be breaking the user's program with an error.
"""

# TODO: Test code capture resilience
# TODO: Test postprocess input/output resilience
from collections import Counter
from typing import Callable

import pytest

import weave
from tests.trace.util import DummyTestException
from weave.trace.context import call_context
from weave.trace.context.tests_context import raise_on_captured_errors
from weave.trace.patcher import MultiPatcher, SymbolPatcher


def assert_no_current_call():
    assert call_context.get_current_call() is None


def test_resilience_to_user_code_errors(client):
    def do_test():
        @weave.op
        def throws():
            raise DummyTestException("This is a test exception")

        throws()

    # The user's exception should be raised - even if we're capturing errors
    with raise_on_captured_errors(True):
        with pytest.raises(DummyTestException):
            do_test()

    # The user's exception should be raised - even if we're not capturing errors
    with pytest.raises(DummyTestException):
        do_test()

    assert_no_current_call()


@pytest.mark.disable_logging_error_check
def test_resilience_to_server_errors(client_with_throwing_server, log_collector):
    def do_test():
        @weave.op
        def simple_op():
            return "hello"

        return simple_op()

    # The user's exception should be raised - even if we're capturing errors
    with raise_on_captured_errors(True):
        with pytest.raises(DummyTestException):
            do_test()

    # We should gracefully handle the error and return a value
    res = do_test()
    assert res == "hello"

    assert_no_current_call()

    logs = log_collector.get_error_logs()
    ag_res = Counter([k.split(", req:")[0] for k in {l.msg for l in logs}])
    # Tim: This is very specific and intentiaion, please don't change
    # this unless you are sure that is the expected behavior
    assert ag_res == {
        "Task failed: DummyTestException: ('FAILURE - call_end": 1,
        "Task failed: DummyTestException: ('FAILURE - file_create": 1,
        "Task failed: DummyTestException: ('FAILURE - obj_create": 1,
    }


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
