import logging
import os
import pathlib
import shutil
import typing

import pytest
from flask.testing import FlaskClient

from weave.legacy.weave import client as client_legacy
from weave.legacy.weave import context_state, environment, io_service, serialize
from weave.legacy.weave.language_features.tagging.tag_store import (
    isolated_tagging_context,
)

from weave.legacy.weave import logs
# from .tests.wandb_system_tests_conftest import *

logs.configure_logger()

# Lazy mode was the default for a long time. Eager is now the default for the user API.
# A lot of tests are written to expect lazy mode, so just make lazy mode the default for
# tests.
context_state._eager_mode.set(False)

# A lot of tests rely on weave.legacy.weave.ops.* being in scope. Importing this here
# makes that work...

### Disable datadog engine tracing

def pytest_sessionstart(session):
    context_state.disable_analytics()


@pytest.fixture(autouse=True)
def pre_post_each_test(test_artifact_dir, caplog):
    # TODO: can't get this to work. I was trying to setup pytest log capture
    # to use our custom log stuff, so that it indents nested logs properly.
    caplog.handler.setFormatter(logging.Formatter(logs.default_log_format))
    # Tests rely on full cache mode right now.
    os.environ["WEAVE_CACHE_MODE"] = "full"
    os.environ["WEAVE_GQL_SCHEMA_PATH"] = str(
        pathlib.Path(__file__).parent.parent.parent / "wb_schema.gql"
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
def eager_mode():
    with context_state.eager_execution():
        yield


@pytest.fixture()
def use_server_gql_schema():
    old_schema_path = environment.gql_schema_path()
    if old_schema_path is not None:
        del os.environ["WEAVE_GQL_SCHEMA_PATH"]
    yield
    if old_schema_path is not None:
        os.environ["WEAVE_GQL_SCHEMA_PATH"] = old_schema_path


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
def http_server_test_client(app):
    from .. import weave_server

    app = weave_server.make_app()
    flask_client = app.test_client()
    return HttpServerTestClient(flask_client)


@pytest.fixture()
def weave_test_client(http_server_test_client):
    return client_legacy.Client(http_server_test_client)




@pytest.fixture()
def ref_tracking():
    with context_state.ref_tracking(True):
        yield


