import os
import random
import numpy as np

import pathlib
import typing
import pytest
import shutil
import tempfile

from weave.panels import table_state
from . import context_state
from .tests import fixture_fakewandb
from . import serialize
from . import client
from .language_features.tagging.tag_store import isolated_tagging_context
from . import logs
from . import io_service
from . import logs
from . import environment
import logging

from flask.testing import FlaskClient

from .tests.wandb_system_tests_conftest import *

from _pytest.config import Config
from _pytest.reports import TestReport
from typing import Tuple, Optional

logs.configure_logger()


def pytest_report_teststatus(
    report: TestReport, config: Config
) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    if report.when == "call":
        duration = "{:.2f}s".format(report.duration)
        if report.failed:
            return "failed", "F", f"FAILED({duration})"
        elif report.passed:
            return "passed", ".", f"PASSED({duration})"
        elif hasattr(
            report, "wasxfail"
        ):  # 'xfail' means that the test was expected to fail
            return report.outcome, "x", "XFAIL"
        elif report.skipped:
            return report.outcome, "s", "SKIPPED"

    elif report.when in ("setup", "teardown"):
        if report.failed:
            return "error", "E", "ERROR"

    return None, None, None


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


@pytest.fixture()
def test_artifact_dir():
    return "/tmp/weave/pytest/%s" % os.environ.get("PYTEST_CURRENT_TEST")


def pytest_collection_modifyitems(config, items):
    # Get the job number from environment variable (0 for even tests, 1 for odd tests)
    job_num = config.getoption("--job-num", default=None)
    if job_num is None:
        return

    job_num = int(job_num)

    selected_items = []
    for index, item in enumerate(items):
        if index % 2 == job_num:
            selected_items.append(item)

    items[:] = selected_items


@pytest.fixture(autouse=True)
def pre_post_each_test(test_artifact_dir, caplog):
    # TODO: can't get this to work. I was trying to setup pytest log capture
    # to use our custom log stuff, so that it indents nested logs properly.
    caplog.handler.setFormatter(logging.Formatter(logs.default_log_format))
    # Tests rely on full cache mode right now.
    os.environ["WEAVE_CACHE_MODE"] = "full"
    os.environ["WEAVE_GQL_SCHEMA_PATH"] = str(
        pathlib.Path(__file__).parent.parent / "wb_schema.gql"
    )
    try:
        shutil.rmtree(test_artifact_dir)
    except (FileNotFoundError, OSError):
        pass
    os.environ["WEAVE_LOCAL_ARTIFACT_DIR"] = test_artifact_dir
    with isolated_tagging_context():
        yield
    del os.environ["WEAVE_LOCAL_ARTIFACT_DIR"]


@pytest.fixture()
def cache_mode_minimal():
    os.environ["WEAVE_NO_CACHE"] = "true"
    yield
    del os.environ["WEAVE_NO_CACHE"]


@pytest.fixture()
def fresh_server_logfile():
    def _clearlog():
        try:
            os.remove(logs.default_log_filename())
        except (OSError, FileNotFoundError) as e:
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
    yield setup_response
    fixture_fakewandb.teardown(setup_response)


@pytest.fixture()
def use_server_gql_schema():
    old_schema_path = environment.gql_schema_path()
    if old_schema_path is not None:
        del os.environ["WEAVE_GQL_SCHEMA_PATH"]
    yield
    if old_schema_path is not None:
        os.environ["WEAVE_GQL_SCHEMA_PATH"] = old_schema_path


@pytest.fixture()
def fixed_random_seed():
    random.seed(8675309)
    np.random.seed(8675309)
    yield
    random.seed(None)
    np.random.seed(None)


@pytest.fixture()
def app():
    from . import weave_server

    app = weave_server.make_app()
    app.config.update(
        {
            "TESTING": True,
        }
    )

    yield app


class HttpServerTestClient:
    def __init__(self, flask_test_client: FlaskClient):
        """Constructor.

        Args:
            flask_test_client: A flask test client to use for sending requests to the test application
        """
        self.flask_test_client = flask_test_client
        self.execute_endpoint = "/__weave/execute"

    def execute(
        self,
        nodes,
        headers: typing.Optional[dict[str, typing.Any]] = None,
        no_cache=False,
    ):
        _headers: dict[str, typing.Any] = {}
        if headers is not None:
            _headers = headers

        serialized = serialize.serialize(nodes)
        r = self.flask_test_client.post(
            self.execute_endpoint,
            json={"graphs": serialized},
            headers=_headers,
        )

        return r.json["data"]


@pytest.fixture()
def http_server_test_client(app):
    from . import weave_server

    app = weave_server.make_app()
    flask_client = app.test_client()
    return HttpServerTestClient(flask_client)


@pytest.fixture()
def weave_test_client(http_server_test_client):
    return client.Client(http_server_test_client)


@pytest.fixture()
def enable_touch_on_read():
    os.environ["WEAVE_ENABLE_TOUCH_ON_READ"] = "1"
    yield
    del os.environ["WEAVE_ENABLE_TOUCH_ON_READ"]


@pytest.fixture()
def io_server_factory():
    original_server = io_service.SERVER

    def factory(process=False):
        server = io_service.Server(process=process)
        server.start()
        io_service.SERVER = server
        return server

    yield factory

    if io_service.SERVER and io_service.SERVER is not original_server:
        io_service.SERVER.shutdown()

    io_service.SERVER = original_server


@pytest.fixture()
def consistent_table_col_ids():
    with table_state.use_consistent_col_ids():
        yield
