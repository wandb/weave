# Uncomment these to run tests of our test reporting plugin that shows test durations.
# Dont run by default as these include tests that error and fail by design.
"""
import pytest


@pytest.fixture()
def error_fixture():
    raise Exception()


def test_ok():
    assert True


def test_fail():
    assert False


def test_error(error_fixture):
    pass


def test_skip():
    pytest.skip("skipping this test")


def test_xfail():
    pytest.xfail("xfailing this test")


@pytest.mark.flaky(reruns=1)
def test_rerun():
    assert False
"""
