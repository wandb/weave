import time
import urllib

import requests


def check_server_up(host, port, num_retries=30) -> bool:
    """Check if a server is up and healthy at the given host:port.

    Args:
        host: The hostname to check
        port: The port to check
        num_retries: Number of retries to attempt (default 30)

    Returns:
        bool: True if server is healthy, False otherwise
    """
    base_url = f"http://{host}:{port}/"
    endpoint = "ping"

    return _check_server_health(
        base_url=base_url, endpoint=endpoint, num_retries=num_retries
    )


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
