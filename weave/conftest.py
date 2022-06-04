import os

import pytest
import shutil


### Disable datadog engine tracing


class FakeTracer:
    def trace(*args, **kwargs):
        pass


def make_fake_tracer():
    return FakeTracer()


from . import engine_trace


### End disable datadog engine tracing

### disable internet access

import socket


def guard(*args, **kwargs):
    raise Exception("I told you not to use the Internet!")


### End disable internet access

# Uncomment these two lines to disable internet access entirely.
# engine_trace.tracer = make_fake_tracer
# socket.socket = guard


def pytest_sessionstart(session):
    context.disable_analytics()


from . import context
from . import weave_server
from .artifacts_local import LOCAL_ARTIFACT_DIR


@pytest.fixture(autouse=True)
def pre_post_each_test():
    try:
        shutil.rmtree(LOCAL_ARTIFACT_DIR)
    except (FileNotFoundError, OSError):
        pass
    yield


@pytest.fixture()
def fresh_server_logfile():
    def _clearlog():
        try:
            os.remove(weave_server.default_log_filename)
        except (OSError, FileNotFoundError):
            pass

    _clearlog()
    yield
    _clearlog()
