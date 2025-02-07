import io
import os
import sys
import time
import timeit

import weave
from weave.trace.constants import TRACE_CALL_EMOJI
from weave.trace.settings import UserSettings, parse_and_apply_settings


@weave.op
def func():
    return 1


def test_disabled_setting(client):
    parse_and_apply_settings(UserSettings(disabled=True))
    disabled_time = timeit.timeit(func, number=10)

    parse_and_apply_settings(UserSettings(disabled=False))
    enabled_time = timeit.timeit(func, number=10)

    assert disabled_time * 10 < enabled_time, (
        "Disabled weave should be faster than enabled weave"
    )


def test_disabled_env(client):
    os.environ["WEAVE_DISABLED"] = "true"
    disabled_time = timeit.timeit(func, number=10)

    os.environ["WEAVE_DISABLED"] = "false"
    enabled_time = timeit.timeit(func, number=10)

    assert disabled_time * 10 < enabled_time, (
        "Disabled weave should be faster than enabled weave"
    )


def test_disabled_env_client():
    os.environ["WEAVE_DISABLED"] = "true"
    client = weave.init("entity/project")

    # Verify that the client is disabled
    # Would be nicer to have a specific property
    assert client.project == "DISABLED"

    @weave.op
    def func():
        return 1

    assert func() == 1

    # No error implies that no calls were sent to the server
    # since this would require writing to `entity/project`
    client._flush()

    os.environ["WEAVE_DISABLED"] = "false"


def test_print_call_link_setting(client):
    captured_stdout = io.StringIO()
    sys.stdout = captured_stdout

    parse_and_apply_settings(UserSettings(print_call_link=False))
    func()

    output = captured_stdout.getvalue()
    assert TRACE_CALL_EMOJI not in output

    parse_and_apply_settings(UserSettings(print_call_link=True))
    func()

    output = captured_stdout.getvalue()
    assert TRACE_CALL_EMOJI in output


def test_print_call_link_env(client):
    captured_stdout = io.StringIO()
    sys.stdout = captured_stdout

    os.environ["WEAVE_PRINT_CALL_LINK"] = "false"
    func()

    output = captured_stdout.getvalue()
    assert TRACE_CALL_EMOJI not in output

    os.environ["WEAVE_PRINT_CALL_LINK"] = "true"
    func()

    output = captured_stdout.getvalue()
    assert TRACE_CALL_EMOJI in output


def test_should_capture_code_setting(client):
    parse_and_apply_settings(UserSettings(capture_code=False))

    @weave.op
    def test_func():
        return 1

    ref = weave.publish(test_func)
    test_func2 = ref.get()
    code2 = test_func2.get_captured_code()
    assert "Code-capture was disabled" in code2

    parse_and_apply_settings(UserSettings(capture_code=True))

    # TODO: Not safe to change capture_code setting mid-script because the op's ref
    # does not know about the setting change.
    @weave.op
    def test_func():
        return 1

    ref2 = weave.publish(test_func)
    test_func3 = ref2.get()
    code3 = test_func3.get_captured_code()
    assert "Code-capture was disabled" not in code3


def test_should_capture_code_env(client):
    os.environ["WEAVE_CAPTURE_CODE"] = "false"

    @weave.op
    def test_func():
        return 1

    ref = weave.publish(test_func)
    test_func2 = ref.get()
    code2 = test_func2.get_captured_code()
    assert "Code-capture was disabled" in code2

    os.environ["WEAVE_CAPTURE_CODE"] = "true"

    @weave.op
    def test_func():
        return 1

    ref2 = weave.publish(test_func)
    test_func3 = ref2.get()
    code3 = test_func3.get_captured_code()
    assert "Code-capture was disabled" not in code3


def slow_operation():
    time.sleep(1)


def speed_test(client, count=5):
    start = time.time()
    futs = [client.future_executor.defer(slow_operation) for _ in range(count)]
    queue_time = time.time()
    for fut in futs:
        fut.result()
    end = time.time()

    queue_time_s = queue_time - start
    wait_time_s = end - queue_time
    return wait_time_s, queue_time_s


# def test_client_parallelism_setting(client_creator):
#     with client_creator() as client:
#         assert client.future_executor._max_workers == None
#         assert client.future_executor._executor._max_workers > 0

#     parse_and_apply_settings(UserSettings(client_parallelism=0))
#     with client_creator() as client:
#         assert client.future_executor._max_workers == 0
#         assert client.future_executor._executor == None
#         wait_time_0, queue_time_0 = speed_test(client)

#     parse_and_apply_settings(UserSettings(client_parallelism=1))
#     with client_creator() as client:
#         assert client.future_executor._max_workers == 1
#         assert client.future_executor._executor._max_workers == 1
#         wait_time_1, queue_time_1 = speed_test(client)

#     # Assert that the queue time is much less for 1 than 0
#     assert queue_time_0 > queue_time_1
#     # Assert that the total time is about the same
#     assert wait_time_0 + queue_time_0 == pytest.approx(
#         wait_time_1 + queue_time_1, abs=0.1
#     )

#     parse_and_apply_settings(UserSettings(client_parallelism=10))
#     with client_creator() as client:
#         assert client.future_executor._max_workers == 10
#         assert client.future_executor._executor._max_workers == 10
#         wait_time_10, queue_time_10 = speed_test(client)

#     # Assert that the queue time is about the same for 10 and 1
#     assert queue_time_1 == pytest.approx(queue_time_10, abs=0.1)
#     # Assert that the wait time is much less for 10 than 1
#     assert wait_time_1 > wait_time_10

#     # Test explicit None
#     parse_and_apply_settings(UserSettings(client_parallelism=None))
#     with client_creator() as client:
#         assert client.future_executor._max_workers == None
#         assert client.future_executor._executor._max_workers > 0
