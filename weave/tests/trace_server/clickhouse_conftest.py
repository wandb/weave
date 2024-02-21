

import pytest


import subprocess
import time
from typing import Tuple
import requests
import urllib



@pytest.fixture(scope="session")
def clickhouse_server():
    (host, port, server_up) = _check_server_up()
    if not server_up:
        pytest.fail("clickhouse server is not running")
    yield (host, port)




def _check_server_health(
    base_url: str, endpoint: str, num_retries: int = 1, sleep_time: int = 1
) -> bool:
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



def _check_server_up(host="localhost", port=18123) -> Tuple[str, int, bool]:
    base_port = 18123
    base_url = f'http://{host}:{port}/'
    endpoint = "/"

    def server_healthy(num_retries=1):
        return _check_server_health(base_url=base_url, endpoint=endpoint, num_retries=num_retries)

    
    if server_healthy():
        return (host, port, True)

    subprocess.Popen([
        "docker",
        "run",
        "-d",
        "--rm",
        "-p",
        f"{base_port}:8123",
        # "-p19000:9000",
        "--name",
        "weave-python-test-clickhouse-server",
        "--ulimit",
        "nofile=262144:262144",
        "clickhouse/clickhouse-server"
    ])
    
    # wait for the server to start
    if server_healthy(num_retries=30):
        return (host, port, True)
    else:
        return (host, port, False)

