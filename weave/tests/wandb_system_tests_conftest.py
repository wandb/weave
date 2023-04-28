import dataclasses
import os
import platform
import secrets
import string
import subprocess

# import threading
import time
import unittest.mock
import urllib.parse

from contextlib import contextmanager

# from pathlib import Path
# from queue import Empty, Queue
from typing import Any, Generator, Optional, Union, Literal

import pytest
import requests
import wandb
import wandb.old.settings
import wandb.util

from weave.wandb_api import wandb_api_context, WandbApiContext

# # `local-testcontainer` ports
LOCAL_BASE_PORT = "8080"
SERVICES_API_PORT = "8083"
FIXTURE_SERVICE_PORT = "9015"


def pytest_addoption(parser):
    # note: we default to "function" scope to ensure the environment is
    # set up properly when running the tests in parallel with pytest-xdist.
    parser.addoption(
        "--user-scope",
        default="function",  # or "function" or "session" or "module"
        help='cli to set scope of fixture "user-scope"',
    )
    parser.addoption(
        "--base-url",
        default=f"http://localhost:{LOCAL_BASE_PORT}",
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


def random_string(length: int = 12) -> str:
    """Generate a random string of a given length.

    :param length: Length of the string to generate.
    :return: Random string.
    """
    return "".join(
        secrets.choice(string.ascii_lowercase + string.digits) for _ in range(length)
    )


def determine_scope(fixture_name, config):
    return config.getoption("--user-scope")


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
            "--name",
            "wandb-local",
            "--platform",
            "linux/amd64",
            # TODO: use the latest image from GAR
            f"gcr.io/wandb-production/local-testcontainer:{wandb_server_tag}",
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
        cmd: Union[UserFixtureCommand, AddAdminAndEnsureNoDefaultUser]
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


@contextmanager
def _become_user(api_key, entity, username, base_url):
    with unittest.mock.patch.dict(
        os.environ,
        {
            "WANDB_API_KEY": api_key,
            "WANDB_ENTITY": entity,
            "WANDB_USERNAME": username,
            "WANDB_BASE_URL": base_url,
        },
    ):
        with wandb_api_context(WandbApiContext(api_key=api_key)):
            yield


@pytest.fixture(scope=determine_scope)
def become_test_user(
    worker_id: str, fixture_fn, base_url, wandb_debug
) -> Generator[str, None, None]:
    username = f"user-{worker_id}-{random_string()}"
    command = UserFixtureCommand(command="up", username=username)
    fixture_fn(command)
    command = UserFixtureCommand(
        command="password", username=username, password=username
    )
    fixture_fn(command)

    with _become_user(username, username, username, base_url):
        yield username

        if not wandb_debug:
            command = UserFixtureCommand(command="down", username=username)
            fixture_fn(command)


@pytest.fixture(scope="session", autouse=True)
def env_teardown():
    wandb.teardown()
    yield
    wandb.teardown()
