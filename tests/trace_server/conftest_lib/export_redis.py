"""Dedicated local Redis for export-admission concurrency tests."""

import json
import subprocess
import time

import pytest
import redis

from weave.trace_server import export_admission


@pytest.fixture(scope="session")
def export_redis_server():
    container = subprocess.check_output(
        [
            "docker",
            "run",
            "--rm",
            "-d",
            "-p",
            "127.0.0.1::6379",
            "redis:7-alpine",
        ],
        text=True,
    ).strip()
    try:
        info = json.loads(subprocess.check_output(["docker", "inspect", container]))[0]
        port = info["NetworkSettings"]["Ports"]["6379/tcp"][0]["HostPort"]
        client = redis.Redis(
            host="127.0.0.1",
            port=int(port),
            decode_responses=True,
            socket_connect_timeout=1,
            socket_timeout=1,
        )
        deadline = time.monotonic() + 10
        while True:
            try:
                client.ping()
                break
            except redis.RedisError:
                if time.monotonic() >= deadline:
                    raise
                time.sleep(0.05)
        yield client
    finally:
        subprocess.run(["docker", "stop", container], check=True, capture_output=True)


@pytest.fixture
def export_redis(export_redis_server, monkeypatch):
    export_redis_server.delete(export_admission.LEASE_KEY, export_admission.ACTIVE_KEY)
    monkeypatch.setattr(
        export_admission, "get_redis_client", lambda: export_redis_server
    )
    yield export_redis_server
    export_redis_server.delete(export_admission.LEASE_KEY, export_admission.ACTIVE_KEY)
