import os

import pytest
import shutil
import tempfile
from . import context_state
from . import weave_server
from . import fixture_fakewandb


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
    context_state.disable_analytics()


@pytest.fixture(autouse=True)
def pre_post_each_test():
    test_artifact_dir = "/tmp/weave/pytest/%s" % os.environ.get("PYTEST_CURRENT_TEST")
    try:
        shutil.rmtree(test_artifact_dir)
    except (FileNotFoundError, OSError):
        pass
    os.environ["WEAVE_LOCAL_ARTIFACT_DIR"] = test_artifact_dir
    yield
    del os.environ["WEAVE_LOCAL_ARTIFACT_DIR"]


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


@pytest.fixture()
def cereal_csv():
    with tempfile.TemporaryDirectory() as d:
        cereal_path = os.path.join(d, "cereal.csv")
        shutil.copy("testdata/cereal.csv", cereal_path)
        yield cereal_path


@pytest.fixture()
def fake_wandb():
    setup_response = fixture_fakewandb.setup()
    yield
    fixture_fakewandb.teardown(setup_response)
