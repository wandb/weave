import asyncio
import dataclasses
import logging
import os
import time
import timeit
import typing
from unittest import mock

import pytest
import tenacity

import weave
from tests.trace.util import (
    capture_output,
    flush_and_wait_for_output,
    flush_output,
)
from weave.trace.constants import TRACE_CALL_EMOJI, TRACE_OBJECT_EMOJI
from weave.trace.display.term import configure_logger
from weave.trace.settings import (
    UserSettings,
    _SettingsOverrides,
    client_parallelism,
    http_timeout,
    max_calls_queue_size,
    override_settings,
    parse_and_apply_settings,
    redact_pii_fields,
    replace_settings,
    should_disable_weave,
    should_print_call_link,
    should_redact_pii,
)
from weave.trace.weave_client import get_parallelism_settings
from weave.utils.retry import with_retry

configure_logger()


@weave.op
def func():
    return 1


def test_disabled_setting(client):
    replace_settings(UserSettings(disabled=True))
    disabled_time = timeit.timeit(func, number=10)
    calls = list(client.get_calls())
    assert len(calls) == 0

    replace_settings(UserSettings(disabled=False))
    enabled_time = timeit.timeit(func, number=10)
    calls = list(client.get_calls())
    assert len(calls) == 10

    assert disabled_time * 10 < enabled_time, (
        "Disabled weave should be faster than enabled weave"
    )


def test_disabled_env(client):
    os.environ["WEAVE_DISABLED"] = "true"
    disabled_time = timeit.timeit(func, number=10)
    calls = list(client.get_calls())
    assert len(calls) == 0

    os.environ["WEAVE_DISABLED"] = "false"
    enabled_time = timeit.timeit(func, number=10)
    calls = list(client.get_calls())
    assert len(calls) == 10

    assert disabled_time * 10 < enabled_time, (
        "Disabled weave should be faster than enabled weave"
    )


def test_publish_when_disabled(weave_active, monkeypatch):
    """Test that weave.publish() returns a dummy ref when WEAVE_DISABLED=true."""
    monkeypatch.setenv("WEAVE_DISABLED", "true")

    with mock.patch(
        "weave.trace.api.weave_client_context.require_weave_client"
    ) as mock_require_client:
        ref = weave.publish({"foo": "bar"}, name="test_obj")
        mock_require_client.assert_not_called()

    assert ref.entity == "DISABLED"
    assert ref.project == "DISABLED"
    assert ref.name == "test_obj"
    assert ref.digest == "DISABLED"


def test_publish_when_disabled_uses_obj_name(weave_active, monkeypatch):
    """Test that publish uses object's name attribute when no explicit name given."""
    monkeypatch.setenv("WEAVE_DISABLED", "true")

    class NamedObj:
        name = "my_obj"

    # Assert there is no network call made
    with mock.patch(
        "weave.trace.api.weave_client_context.require_weave_client"
    ) as mock_require_client:
        ref = weave.publish(NamedObj())
        mock_require_client.assert_not_called()

    assert ref.name == "my_obj"


def test_publish_when_disabled_uses_class_name(weave_active, monkeypatch):
    """Test that publish uses class name when object has no name attribute."""
    monkeypatch.setenv("WEAVE_DISABLED", "true")

    class MyClass:
        pass

    # Assert there is no network call made
    with mock.patch(
        "weave.trace.api.weave_client_context.require_weave_client"
    ) as mock_require_client:
        ref = weave.publish(MyClass())
        mock_require_client.assert_not_called()

    assert ref.name == "MyClass"


def test_publish_when_disabled_ignores_tags_aliases(weave_active, monkeypatch):
    """Tags and aliases should be silently ignored when weave is disabled."""
    monkeypatch.setenv("WEAVE_DISABLED", "true")

    with mock.patch(
        "weave.trace.api.weave_client_context.require_weave_client"
    ) as mock_require_client:
        ref = weave.publish(
            {"data": "test"},
            name="disabled_obj",
            tags=["prod"],
            aliases=["v1"],
        )
        mock_require_client.assert_not_called()

    assert ref.entity == "DISABLED"
    assert ref.digest == "DISABLED"


def test_print_call_link_setting(client_creator):
    with client_creator(settings=UserSettings(print_call_link=False)) as client:
        with capture_output() as captured:
            func()
            flush_output(client)
    assert TRACE_CALL_EMOJI not in captured.getvalue()

    with client_creator(settings=UserSettings(print_call_link=True)) as client:
        with capture_output() as captured:
            func()
            assert flush_and_wait_for_output(client, captured, TRACE_CALL_EMOJI)
    assert TRACE_CALL_EMOJI in captured.getvalue()


def test_print_call_link_env(client):
    os.environ["WEAVE_PRINT_CALL_LINK"] = "false"
    with capture_output() as captured:
        func()
        flush_output(client)

    assert TRACE_CALL_EMOJI not in captured.getvalue()

    os.environ["WEAVE_PRINT_CALL_LINK"] = "true"
    with capture_output() as captured:
        func()
        assert flush_and_wait_for_output(client, captured, TRACE_CALL_EMOJI)

    assert TRACE_CALL_EMOJI in captured.getvalue()

    # Clean up after test
    del os.environ["WEAVE_PRINT_CALL_LINK"]


def test_should_capture_code_setting(weave_active):
    replace_settings(UserSettings(capture_code=False))

    @weave.op
    def test_func():
        return 1

    ref = weave.publish(test_func)
    test_func2 = ref.get()
    code2 = test_func2.get_captured_code()
    assert "Code-capture was disabled" in code2

    replace_settings(UserSettings(capture_code=True))

    # TODO: Not safe to change capture_code setting mid-script because the op's ref
    # does not know about the setting change.
    @weave.op
    def test_func():
        return 1

    ref2 = weave.publish(test_func)
    test_func3 = ref2.get()
    code3 = test_func3.get_captured_code()
    assert "Code-capture was disabled" not in code3


def test_should_capture_code_env(weave_active):
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
    time.sleep(0.1)


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


def test_client_parallelism_setting(client_creator):
    with mock.patch("os.cpu_count", return_value=4):
        with client_creator() as client:
            assert client.future_executor._max_workers == 4
            assert client.future_executor._executor._max_workers == 4

    replace_settings(UserSettings(client_parallelism=1))
    with mock.patch("os.cpu_count", return_value=4):
        with client_creator() as client:
            assert client.future_executor._max_workers == 1
            assert client.future_executor._executor._max_workers == 1
            wait_time_1, queue_time_1 = speed_test(client)

    replace_settings(UserSettings(client_parallelism=10))
    with client_creator() as client:
        assert client.future_executor._max_workers == 5
        assert client.future_executor._executor._max_workers == 5
        assert client.future_executor_fastlane._max_workers == 5
        wait_time_10, queue_time_10 = speed_test(client)

    # Assert that the queue time is about the same for 10 and 1
    assert queue_time_1 == pytest.approx(queue_time_10, abs=0.5)
    # Assert that the wait time is much less for 10 than 1
    assert wait_time_1 > wait_time_10

    # Test explicit None
    replace_settings(UserSettings(client_parallelism=None))
    with mock.patch("os.cpu_count", return_value=4):
        with client_creator() as client:
            assert client.future_executor._max_workers == 4
            assert client.future_executor._executor._max_workers > 0


def test_get_parallelism_settings() -> None:
    # Test default behavior with 4 CPU cores
    with mock.patch("os.cpu_count", return_value=4):
        main, upload = get_parallelism_settings()
        assert main == 4
        assert upload == 4

    # Test explicit total parallelism override
    with mock.patch.dict(os.environ, {"WEAVE_CLIENT_PARALLELISM": "10"}):
        main, upload = get_parallelism_settings()
        assert main == 5
        assert upload == 5

    # Test disabling parallelism
    with mock.patch.dict(os.environ, {"WEAVE_CLIENT_PARALLELISM": "0"}):
        main, upload = get_parallelism_settings()
        assert main == 0
        assert upload == 0

    # Test max cap with many cores
    with mock.patch("os.cpu_count", return_value=64):
        main, upload = get_parallelism_settings()
        assert main == 16
        assert upload == 16

    # Test single core system
    with mock.patch("os.cpu_count", return_value=1):
        main, upload = get_parallelism_settings()
        assert main == 2
        assert upload == 3

    # Test when cpu_count returns None
    with mock.patch("os.cpu_count", return_value=None):
        main, upload = get_parallelism_settings()
        assert main == 2
        assert upload == 3


def test_retry_max_attempts_settings(client_creator, caplog) -> None:
    caplog.set_level(logging.INFO, logger="weave.utils.retry")

    @with_retry
    def func():
        raise RuntimeError("Test error")

    with client_creator(settings=UserSettings(retry_max_attempts=2)) as client:
        with pytest.raises(RuntimeError):
            func()

    retry_attempt_logs = [r for r in caplog.records if r.msg == "retry_attempt"]
    retry_failed_logs = [r for r in caplog.records if r.msg == "retry_failed"]

    assert len(retry_attempt_logs) == 1
    attempt_log = retry_attempt_logs[0]
    assert attempt_log.attempt_number == 1
    assert "Test error" in attempt_log.exception

    assert len(retry_failed_logs) == 1
    failed_log = retry_failed_logs[0]
    assert failed_log.attempt_number == 2
    assert "Test error" in failed_log.exception


def test_retry_max_attempts_env(caplog) -> None:
    os.environ["WEAVE_RETRY_MAX_ATTEMPTS"] = "2"
    caplog.set_level(logging.INFO, logger="weave.utils.retry")

    @with_retry
    def func():
        raise RuntimeError("Test error")

    with pytest.raises(RuntimeError):
        func()

    retry_attempt_logs = [r for r in caplog.records if r.msg == "retry_attempt"]
    retry_failed_logs = [r for r in caplog.records if r.msg == "retry_failed"]

    assert len(retry_attempt_logs) == 1
    attempt_log = retry_attempt_logs[0]
    assert attempt_log.attempt_number == 1
    assert "Test error" in attempt_log.exception

    assert len(retry_failed_logs) == 1
    failed_log = retry_failed_logs[0]
    assert failed_log.attempt_number == 2
    assert "Test error" in failed_log.exception

    del os.environ["WEAVE_RETRY_MAX_ATTEMPTS"]


def test_retry_max_interval_settings(client_creator, caplog, monkeypatch) -> None:
    caplog.set_level(logging.INFO, logger="weave.utils.retry")

    call_args = []

    def mock_wait_exponential_jitter(initial=0, max=None):
        call_args.append(max)
        return tenacity.wait_none()

    monkeypatch.setattr(
        tenacity, "wait_exponential_jitter", mock_wait_exponential_jitter
    )

    @with_retry
    def func():
        raise RuntimeError("Test error")

    custom_max_interval = 30.0
    with client_creator(settings=UserSettings(retry_max_interval=custom_max_interval)):
        with pytest.raises(RuntimeError):
            func()

    assert custom_max_interval in call_args


def test_retry_max_interval_env(caplog, monkeypatch) -> None:
    os.environ["WEAVE_RETRY_MAX_INTERVAL"] = "25.0"
    caplog.set_level(logging.INFO, logger="weave.utils.retry")

    original_wait = tenacity.wait_exponential_jitter
    call_args = []

    def mock_wait_exponential_jitter(initial=0, max=None):
        call_args.append(max)
        return original_wait(initial=initial, max=max)

    monkeypatch.setattr(
        tenacity, "wait_exponential_jitter", mock_wait_exponential_jitter
    )

    @with_retry
    def func():
        raise RuntimeError("Test error")

    with pytest.raises(RuntimeError):
        func()

    assert 25.0 in call_args

    del os.environ["WEAVE_RETRY_MAX_INTERVAL"]


def test_log_level_setting(client_creator):
    """Test that log_level setting properly silences publish messages."""

    @weave.op
    def test_func():
        return 1

    # Test with ERROR level - should NOT see publish messages
    with client_creator(settings=UserSettings(log_level="ERROR")) as client:
        with capture_output() as captured:
            weave.publish(test_func, name="test_func_error")
    output = captured.getvalue()
    assert TRACE_OBJECT_EMOJI not in output
    assert "Published to" not in output

    # Test with INFO level - should see publish messages
    with client_creator(settings=UserSettings(log_level="INFO")) as client:
        with capture_output() as captured:
            weave.publish(test_func, name="test_func_info")
    output = captured.getvalue()
    assert TRACE_OBJECT_EMOJI in output
    assert "Published to" in output


def test_log_level_env(client_creator):
    """Test that WEAVE_LOG_LEVEL environment variable properly silences publish messages."""

    @weave.op
    def test_func():
        return 1

    # Test with ERROR level - should NOT see publish messages
    os.environ["WEAVE_LOG_LEVEL"] = "ERROR"
    with client_creator() as client:
        with capture_output() as captured:
            weave.publish(test_func, name="test_func_error_env")
    output = captured.getvalue()
    assert TRACE_OBJECT_EMOJI not in output
    assert "Published to" not in output

    # Test with INFO level - should see publish messages
    os.environ["WEAVE_LOG_LEVEL"] = "INFO"
    with client_creator() as client:
        with capture_output() as captured:
            weave.publish(test_func, name="test_func_info_env")
    output = captured.getvalue()
    assert TRACE_OBJECT_EMOJI in output
    assert "Published to" in output

    # Clean up after test
    del os.environ["WEAVE_LOG_LEVEL"]


@pytest.fixture
def clean_settings_env(monkeypatch):
    """Strip all WEAVE_* env vars and reset settings to defaults for the test."""
    weave_keys = [k for k in os.environ if k.startswith("WEAVE_")]
    for key in weave_keys:
        monkeypatch.delenv(key, raising=False)
    replace_settings()
    yield
    replace_settings()


@pytest.mark.usefixtures("clean_settings_env")
class TestReplaceSettings:
    def test_installs_snapshot(self):
        replace_settings(UserSettings(disabled=True, print_call_link=False))
        assert should_disable_weave() is True
        assert should_print_call_link() is False

    def test_resets_unmentioned_fields(self):
        replace_settings(UserSettings(disabled=True, print_call_link=False))
        # Replacing with a fresh UserSettings(disabled=True) should NOT
        # preserve print_call_link=False — replace-all semantics.
        replace_settings(UserSettings(disabled=True))
        assert should_disable_weave() is True
        assert should_print_call_link() is True

    def test_none_resets_to_defaults(self):
        replace_settings(UserSettings(disabled=True))
        assert should_disable_weave() is True
        replace_settings(None)
        assert should_disable_weave() is False

    def test_no_args_resets_to_defaults(self):
        replace_settings(UserSettings(disabled=True))
        replace_settings()
        assert should_disable_weave() is False

    def test_dict_input(self):
        replace_settings({"disabled": True, "redact_pii": True})
        assert should_disable_weave() is True
        assert should_redact_pii() is True

    def test_dict_unknown_field_raises(self):
        with pytest.raises(TypeError):
            replace_settings({"definitely_not_a_real_field": True})

    def test_invalid_type_raises(self):
        with pytest.raises(TypeError):
            replace_settings(42)


@pytest.mark.usefixtures("clean_settings_env")
class TestOverrideSettings:
    def test_scopes_one_field(self):
        replace_settings(UserSettings(print_call_link=False))
        assert should_disable_weave() is False
        with override_settings(disabled=True):
            assert should_disable_weave() is True
            # Other fields keep the surrounding snapshot's values
            assert should_print_call_link() is False
        assert should_disable_weave() is False
        assert should_print_call_link() is False

    def test_nested(self):
        with override_settings(disabled=True):
            assert should_disable_weave() is True
            with override_settings(print_call_link=False):
                assert should_disable_weave() is True
                assert should_print_call_link() is False
            assert should_disable_weave() is True
            assert should_print_call_link() is True
        assert should_disable_weave() is False

    def test_unknown_field_raises(self):
        with pytest.raises(TypeError), override_settings(not_a_real_field=True):
            pass

    def test_async_context_does_not_leak(self):
        """Each async context gets its own override stack."""

        async def child():
            with override_settings(disabled=True):
                assert should_disable_weave() is True
                await asyncio.sleep(0)
                assert should_disable_weave() is True

        async def parent():
            # Parent does not override; child should see its own override;
            # parent should not see leakage.
            assert should_disable_weave() is False
            await child()
            assert should_disable_weave() is False

        asyncio.run(parent())


@pytest.mark.usefixtures("clean_settings_env")
class TestEnvOverlay:
    def test_env_var_wins_over_snapshot(self, monkeypatch):
        replace_settings(UserSettings(disabled=False))
        assert should_disable_weave() is False
        monkeypatch.setenv("WEAVE_DISABLED", "true")
        assert should_disable_weave() is True

    def test_env_var_change_takes_effect_immediately(self, monkeypatch):
        """Q2 contract: users may flip env vars mid-process and reads pick it up."""
        assert should_disable_weave() is False
        monkeypatch.setenv("WEAVE_DISABLED", "true")
        assert should_disable_weave() is True
        monkeypatch.setenv("WEAVE_DISABLED", "false")
        assert should_disable_weave() is False
        monkeypatch.delenv("WEAVE_DISABLED")
        assert should_disable_weave() is False

    def test_empty_env_var_falls_through_to_snapshot(self, monkeypatch):
        """An env var that exists but is empty is treated as unset."""
        replace_settings(UserSettings(disabled=True))
        monkeypatch.setenv("WEAVE_DISABLED", "")
        assert should_disable_weave() is True

    def test_coerces_int(self, monkeypatch):
        monkeypatch.setenv("WEAVE_MAX_CALLS_QUEUE_SIZE", "42")
        assert max_calls_queue_size() == 42

    def test_coerces_float(self, monkeypatch):
        monkeypatch.setenv("WEAVE_HTTP_TIMEOUT", "12.5")
        assert http_timeout() == 12.5

    def test_coerces_list(self, monkeypatch):
        monkeypatch.setenv("WEAVE_REDACT_PII_FIELDS", "a,b,c")
        assert redact_pii_fields() == ["a", "b", "c"]

    def test_coerces_optional_int(self, monkeypatch):
        monkeypatch.setenv("WEAVE_CLIENT_PARALLELISM", "7")
        assert client_parallelism() == 7


@pytest.mark.usefixtures("clean_settings_env")
class TestBackCompat:
    def test_parse_and_apply_settings_is_alias_for_replace_settings(self):
        """Back-compat: the prior public name still works."""
        parse_and_apply_settings(UserSettings(disabled=True))
        assert should_disable_weave() is True
        parse_and_apply_settings(None)
        assert should_disable_weave() is False


class TestUserSettingsValue:
    def test_is_frozen(self):
        settings = UserSettings()
        with pytest.raises(dataclasses.FrozenInstanceError):
            settings.disabled = True

    def test_rejects_unknown_kwargs(self):
        with pytest.raises(TypeError):
            UserSettings(not_a_field=True)

    def test_settings_overrides_typeddict_matches_user_settings(self):
        """The _SettingsOverrides TypedDict that types override_settings(**fields)
        must mirror UserSettings exactly (same names, same types).  Drift means
        the types lie to callers.
        """
        user_settings_hints = typing.get_type_hints(UserSettings)
        overrides_hints = typing.get_type_hints(_SettingsOverrides)
        assert user_settings_hints == overrides_hints, (
            "_SettingsOverrides drift: add/update fields to match UserSettings"
        )
