import logging
import os
import pathlib
import shutil
import typing
import random
import tempfile
import numpy as np

import pytest
from flask.testing import FlaskClient

from weave_query.tests import fixture_fakewandb
from weave_query.weave_query import client as client_legacy
from weave_query.weave_query import context_state, environment, io_service, serialize
from weave_query.weave_query.language_features.tagging.tag_store import (
    isolated_tagging_context,
)

from weave_query.weave_query import logs

import contextlib
import dataclasses
import os
import platform
import secrets
import string
import subprocess
import time
import unittest.mock
import urllib.parse
from typing import Any, Generator, Literal, Optional, Union

import filelock
import pytest
import requests
import wandb

from weave_query.weave_query.wandb_api import from_environment, wandb_api_context, WandbApiContext



# Force testing to never report wandb sentry events
os.environ["WANDB_ERROR_REPORTING"] = "false"


class FakeTracer:
    def trace(*args, **kwargs):
        pass


def make_fake_tracer():
    return FakeTracer()


### End disable datadog engine tracing
### disable internet access


def guard(*args, **kwargs):
    raise Exception("I told you not to use the Internet!")


### End disable internet access

# Uncomment these two lines to disable internet access entirely.
# engine_trace.tracer = make_fake_tracer
# socket.socket = guard


@pytest.fixture()
def test_artifact_dir():
    return "/tmp/weave/pytest/%s" % os.environ.get("PYTEST_CURRENT_TEST")


def pytest_sessionfinish(session, exitstatus):
    if exitstatus == pytest.ExitCode.NO_TESTS_COLLECTED:
        print("No tests were selected. Exiting gracefully.")
        session.exitstatus = 0


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
def throw_on_error():
    os.environ["WEAVE_VALUE_OR_ERROR_DEBUG"] = "true"
    yield
    del os.environ["WEAVE_VALUE_OR_ERROR_DEBUG"]


@pytest.fixture()
def cache_mode_minimal():
    os.environ["WEAVE_NO_CACHE"] = "true"
    yield
    del os.environ["WEAVE_NO_CACHE"]


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
def fixed_random_seed():
    random.seed(8675309)
    np.random.seed(8675309)
    yield
    random.seed(None)
    np.random.seed(None)


@pytest.fixture()
def app():
    from weave_query import weave_server

    app = weave_server.make_app()
    app.config.update(
        {
            "TESTING": True,
        }
    )

    yield app


@pytest.fixture()
def enable_touch_on_read():
    os.environ["WEAVE_ENABLE_TOUCH_ON_READ"] = "1"
    yield
    del os.environ["WEAVE_ENABLE_TOUCH_ON_READ"]


@pytest.fixture()
def consistent_table_col_ids():
    from weave_query.weave_query.panels import table_state

    with table_state.use_consistent_col_ids():
        yield


@pytest.fixture()
def strict_op_saving():
    with context_state.strict_op_saving(True):
        yield

logs.configure_logger()

# Lazy mode was the default for a long time. Eager is now the default for the user API.
# A lot of tests are written to expect lazy mode, so just make lazy mode the default for
# tests.
context_state._eager_mode.set(False)

# A lot of tests rely on weave_query.weave_query.ops.* being in scope. Importing this here
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
    from weave_query import weave_server

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


@pytest.fixture(scope="session")
def lock(tmp_path_factory):
    base_temp = tmp_path_factory.getbasetemp()
    lock_file = base_temp.parent / "serial.lock"
    yield filelock.FileLock(lock_file=str(lock_file))
    with contextlib.suppress(OSError):
        os.remove(path=lock_file)


@pytest.fixture()
def serial(lock):
    with lock.acquire(poll_interval=0.1):
        yield


# End of copied code snippet


@dataclasses.dataclass
class LocalBackendFixturePayload:
    username: str
    password: str
    api_key: str
    base_url: str
    cookie: str


def determine_scope(fixture_name, config):
    return config.getoption("--user-scope")


@pytest.fixture(scope=determine_scope)
def bootstrap_user(
    worker_id: str, fixture_fn, base_url, wandb_debug
) -> Generator[LocalBackendFixturePayload, None, None]:
    username = f"user-{worker_id}-{random_string()}"
    command = UserFixtureCommand(command="up", username=username)
    fixture_fn(command)
    command = UserFixtureCommand(
        command="password", username=username, password=username
    )
    fixture_fn(command)

    with unittest.mock.patch.dict(
        os.environ,
        {
            "WANDB_BASE_URL": base_url,
        },
    ):
        yield LocalBackendFixturePayload(
            username=username,
            password=username,
            api_key=username,
            base_url=base_url,
            cookie="NOT-IMPLEMENTED",
        )
        

@pytest.fixture(scope=determine_scope)
def user_by_api_key_in_context(
    bootstrap_user: LocalBackendFixturePayload,
) -> Generator[LocalBackendFixturePayload, None, None]:
    with wandb_api_context(WandbApiContext(api_key=bootstrap_user.api_key)):
        yield bootstrap_user


@pytest.fixture(scope=determine_scope)
def user_by_http_headers_in_context(
    bootstrap_user: LocalBackendFixturePayload,
) -> Generator[LocalBackendFixturePayload, None, None]:
    headers = {
        "use-admin-privileges": "true",
        "cookie": f"wandb={bootstrap_user.cookie};",
    }
    cookies = {"wandb": bootstrap_user.cookie}
    with wandb_api_context(WandbApiContext(headers=headers, cookies=cookies)):
        yield bootstrap_user



@pytest.fixture(scope=determine_scope)
def user_by_api_key_in_env(
    bootstrap_user: LocalBackendFixturePayload, serial
) -> Generator[LocalBackendFixturePayload, None, None]:
    with unittest.mock.patch.dict(
        os.environ,
        {
            "WANDB_API_KEY": bootstrap_user.api_key,
        },
    ):
        with from_environment():
            wandb.teardown()  # type: ignore
            yield bootstrap_user
            wandb.teardown()  # type: ignore


@pytest.fixture(scope=determine_scope)
def user_by_api_key_netrc(
    bootstrap_user: LocalBackendFixturePayload,
) -> Generator[LocalBackendFixturePayload, None, None]:
    netrc_path = os.path.expanduser("~/.netrc")
    old_netrc = None
    if os.path.exists(netrc_path):
        with open(netrc_path, "r") as f:
            old_netrc = f.read()
    try:
        with open(netrc_path, "w") as f:
            url = urllib.parse.urlparse(bootstrap_user.base_url).netloc
            f.write(
                f"machine {url}\n  login user\n  password {bootstrap_user.api_key}\n"
            )
        with from_environment():
            yield bootstrap_user
    finally:
        if old_netrc is None:
            os.remove(netrc_path)
        else:
            with open(netrc_path, "w") as f:
                f.write(old_netrc)


##################################################################
## The following code is a selection copied from the wandb sdk. ##
## wandb/tests/unit_tests/conftest.py                           ##
##################################################################


# # `local-testcontainer` ports
LOCAL_BASE_PORT = "8080"
SERVICES_API_PORT = "8083"
FIXTURE_SERVICE_PORT = "9015"
WB_SERVER_HOST = "http://localhost"


def pytest_addoption(parser):
    # note: we default to "function" scope to ensure the environment is
    # set up properly when running the tests in parallel with pytest-xdist.
    if os.environ.get("WB_SERVER_HOST"):
        wandb_server_host = os.environ["WB_SERVER_HOST"]
    else:
        wandb_server_host = WB_SERVER_HOST

    parser.addoption(
        "--user-scope",
        default="function",  # or "function" or "session" or "module"
        help='cli to set scope of fixture "user-scope"',
    )

    parser.addoption(
        "--job-num",
        default=None,
        help='cli to set "job-num"',
    )

    parser.addoption(
        "--base-url",
        default=f"{wandb_server_host}:{LOCAL_BASE_PORT}",
        help='cli to set "base-url"',
    )
    parser.addoption(
        "--wandb-server-tag",
        default="master",
        help="Image tag to use for the wandb server",
    )
    parser.addoption(
        "--wandb-server-pull",
        action="store_true",
        default=False,
        help="Force pull the latest wandb server image",
    )
    # debug option: creates an admin account that can be used to log in to the
    # app and inspect the test runs.
    parser.addoption(
        "--wandb-debug",
        action="store_true",
        default=False,
        help="Run tests in debug mode",
    )

    parser.addoption(
        "--weave-server",
        action="store",
        default="sqlite",
        help="Specify the client object to use: sqlite or clickhouse",
    )


def random_string(length: int = 12) -> str:
    """Generate a random string of a given length.

    :param length: Length of the string to generate.
    :return: Random string.
    """
    return "".join(
        secrets.choice(string.ascii_lowercase + string.digits) for _ in range(length)
    )


@pytest.fixture(scope="session")
def base_url(request):
    return request.config.getoption("--base-url")


@pytest.fixture(scope="session")
def wandb_server_tag(request):
    return request.config.getoption("--wandb-server-tag")


@pytest.fixture(scope="session")
def wandb_server_pull(request):
    if request.config.getoption("--wandb-server-pull"):
        return "always"
    return "missing"


@pytest.fixture(scope="session")
def wandb_debug(request):
    return request.config.getoption("--wandb-debug", default=False)


def check_server_health(
    base_url: str, endpoint: str, num_retries: int = 1, sleep_time: int = 1
) -> bool:
    """Check if wandb server is healthy.

    :param base_url:
    :param num_retries:
    :param sleep_time:
    :return:
    """
    for _ in range(num_retries):
        try:
            response = requests.get(urllib.parse.urljoin(base_url, endpoint))
            if response.status_code == 200:
                return True
            time.sleep(sleep_time)
        except requests.exceptions.ConnectionError:
            time.sleep(sleep_time)

    print(
        f"Server not healthy @ {urllib.parse.urljoin(base_url, endpoint)}: no response"
    )
    return False


def check_server_up(
    base_url: str,
    wandb_server_tag: str = "master",
    wandb_server_pull: Literal["missing", "always"] = "missing",
) -> bool:
    """Check if wandb server is up and running.

    If not on the CI and the server is not running, then start it first.

    :param base_url:
    :param wandb_server_tag:
    :param wandb_server_pull:
    :return:
    """
    app_health_endpoint = "healthz"
    fixture_url = base_url.replace(LOCAL_BASE_PORT, FIXTURE_SERVICE_PORT)
    fixture_health_endpoint = "health"

    if os.environ.get("CI") == "true":
        return check_server_health(base_url=base_url, endpoint=app_health_endpoint)

    if not check_server_health(base_url=base_url, endpoint=app_health_endpoint):
        # start wandb server locally and expose necessary ports to the host
        command = [
            "docker",
            "run",
            "--pull",
            wandb_server_pull,
            "--rm",
            "-v",
            "wandb:/vol",
            "-p",
            f"{LOCAL_BASE_PORT}:{LOCAL_BASE_PORT}",
            "-p",
            f"{SERVICES_API_PORT}:{SERVICES_API_PORT}",
            "-p",
            f"{FIXTURE_SERVICE_PORT}:{FIXTURE_SERVICE_PORT}",
            "-e",
            "WANDB_ENABLE_TEST_CONTAINER=true",
            *(
                ["-e", "PARQUET_ENABLED=true"]
                if os.environ.get("PARQUET_ENABLED")
                else []
            ),
            "--name",
            "wandb-local",
            "--platform",
            "linux/amd64",
            (
                "us-central1-docker.pkg.dev/wandb-production/images/local-testcontainer:tim-franken_branch_parquet"
                if os.environ.get("PARQUET_ENABLED")
                else f"us-central1-docker.pkg.dev/wandb-production/images/local-testcontainer:{wandb_server_tag}"
            ),
        ]
        subprocess.Popen(command)
        # wait for the server to start
        server_is_up = check_server_health(
            base_url=base_url, endpoint=app_health_endpoint, num_retries=30
        )
        if not server_is_up:
            return False
        # check that the fixture service is accessible
        return check_server_health(
            base_url=fixture_url, endpoint=fixture_health_endpoint, num_retries=30
        )

    return check_server_health(
        base_url=fixture_url, endpoint=fixture_health_endpoint, num_retries=10
    )


@dataclasses.dataclass
class UserFixtureCommand:
    command: Literal["up", "down", "down_all", "logout", "login", "password"]
    username: Optional[str] = None
    password: Optional[str] = None
    admin: bool = False
    endpoint: str = "db/user"
    port: str = FIXTURE_SERVICE_PORT
    method: Literal["post"] = "post"


@dataclasses.dataclass
class AddAdminAndEnsureNoDefaultUser:
    email: str
    password: str
    endpoint: str = "api/users-admin"
    port: str = SERVICES_API_PORT
    method: Literal["put"] = "put"


@pytest.fixture(scope="session")
def fixture_fn(base_url, wandb_server_tag, wandb_server_pull):
    def fixture_util(
        cmd: Union[UserFixtureCommand, AddAdminAndEnsureNoDefaultUser],
    ) -> bool:
        endpoint = urllib.parse.urljoin(
            base_url.replace(LOCAL_BASE_PORT, cmd.port),
            cmd.endpoint,
        )
        data: Any
        if isinstance(cmd, UserFixtureCommand):
            data = {"command": cmd.command}
            if cmd.username:
                data["username"] = cmd.username
            if cmd.password:
                data["password"] = cmd.password
            if cmd.admin is not None:
                data["admin"] = cmd.admin
        elif isinstance(cmd, AddAdminAndEnsureNoDefaultUser):
            data = [
                {"email": f"{cmd.email}@wandb.com", "password": cmd.password},
            ]
        else:
            raise NotImplementedError(f"{cmd} is not implemented")
        # trigger fixture
        print(f"Triggering fixture on {endpoint}: {data}")
        response = getattr(requests, cmd.method)(endpoint, json=data)
        if response.status_code != 200:
            print(response.json())
            return False
        return True

    # todo: remove this once testcontainer is available on Win
    if platform.system() == "Windows":
        pytest.skip("testcontainer is not available on Win")

    if not check_server_up(base_url, wandb_server_tag, wandb_server_pull):
        pytest.fail("wandb server is not running")

    yield fixture_util


@pytest.fixture(scope=determine_scope)
def dev_only_admin_env_override() -> Generator[None, None, None]:
    new_env = {}
    admin_path = "../config/.admin.env"
    if not os.path.exists(admin_path):
        print(
            f"WARNING: Could not find admin env file at {admin_path}. Please follow instructions in README.md to create one."
        )
        yield
        return
    with open(admin_path) as file:
        for line in file:
            # skip comments and blank lines
            if line.startswith("#") or line.strip().__len__() == 0:
                continue
            # otherwise treat lines as environment variables in a KEY=VALUE combo
            key, value = line.split("=", 1)
            new_env[key.strip()] = value.strip()
    with unittest.mock.patch.dict(
        os.environ,
        new_env,
    ):
        yield
