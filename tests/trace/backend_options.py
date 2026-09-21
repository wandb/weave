"""Public pytest options and selection, independent of backend implementation."""

import pytest


def pytest_addoption(parser):
    try:
        parser.addoption(
            "--trace-server",
            action="store",
            default="clickhouse",
            help="Specify the backend to use: clickhouse or fake (in-memory)",
        )
        parser.addoption(
            "--ch",
            "--clickhouse",
            action="store_true",
            help="Use clickhouse server (shorthand for --trace-server=clickhouse)",
        )
        parser.addoption(
            "--clickhouse-process",
            action="store",
            default="false",
            help="Use a clickhouse process instead of a container",
        )
        parser.addoption(
            "--remote-http-trace-server",
            action="store",
            default="remote",
            help="Specify the remote HTTP trace server implementation: remote or stainless",
        )
    except ValueError:
        pass


def pytest_collection_modifyitems(config, items):
    # Add the trace_server marker to:
    # 1. All tests in the trace_server directory (regardless of fixture usage)
    # 2. All tests that use the trace_server fixture (for tests outside this directory)
    # Note: Filtering based on remote-http-trace-server flag is handled in tests/trace_server_bindings/conftest.py
    for item in items:
        if "trace_server" in item.fixturenames or any(
            part in {"trace_server", "trace_server_migrator"}
            for part in item.path.parts
        ):
            item.add_marker(pytest.mark.requires_backend)
        # Check if the test is in the trace_server directory by checking parent directories
        if "trace_server" in item.path.parts:
            item.add_marker(pytest.mark.trace_server)
        # Also mark tests that use the trace_server fixture (for tests outside this dir)
        elif "trace_server" in item.fixturenames:
            item.add_marker(pytest.mark.trace_server)
