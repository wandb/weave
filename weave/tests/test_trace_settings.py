import io
import sys
import time

import weave
from weave.trace.settings import UserSettings, parse_and_apply_settings


def test_disabled(client):
    settings = UserSettings(disabled=True)
    parse_and_apply_settings(settings)

    @weave.op
    def test():
        return 1

    disabled_start = time.time()
    test()
    disabled_end = time.time()
    disabled_delta = disabled_end - disabled_start

    settings2 = UserSettings(disabled=False)
    parse_and_apply_settings(settings2)

    enabled_start = time.time()
    test()
    enabled_end = time.time()
    enabled_delta = enabled_end - enabled_start

    # Regular py func should be a lot faster than traced func
    assert disabled_delta * 10 < enabled_delta


def test_print_call_link_disabled(client):
    captured_stdout = io.StringIO()
    sys.stdout = captured_stdout

    settings = UserSettings(print_call_link=False)
    parse_and_apply_settings(settings)

    @weave.op
    def test():
        return 1

    test()

    output = captured_stdout.getvalue()
    assert output == ""


def test_print_call_link_enabled(client):
    captured_stdout = io.StringIO()
    sys.stdout = captured_stdout

    settings = UserSettings(print_call_link=True)
    parse_and_apply_settings(settings)

    @weave.op
    def test():
        return 1

    test()

    output = captured_stdout.getvalue()
    assert output != ""
