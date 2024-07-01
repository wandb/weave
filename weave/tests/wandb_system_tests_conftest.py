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

from weave.legacy.wandb_api import (
    WandbApiContext,
    from_environment,
    wandb_api_context,
)


# The following code snippet was copied from:
# https://github.com/pytest-dev/pytest-xdist/issues/84#issuecomment-617566804
#
# The purpose of the `serial` fixture is to ensure that any test with `serial`
# must be run serially. This is critical for tests which use environment
# variables for auth since the low level W&B API state ends up being shared
# between tests.
@pytest.fixture(scope="session")
def lock(tmp_path_factory):
    base_temp = tmp_path_factory.getbasetemp()
    lock_file = base_temp.parent / "serial.lock"
    yield filelock.FileLock(lock_file=str(lock_file))
    with contextlib.suppress(OSError):
        os.remove(path=lock_file)


@pytest.fixture()
def serial(lock):
    with lock.acquire(poll_intervall=0.1):
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
