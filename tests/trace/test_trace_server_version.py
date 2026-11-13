"""Tests for trace server version checking."""

import asyncio
from unittest import mock

import httpx
import pytest
from PIL import Image

import weave
from weave.trace import weave_init
from weave.trace.context import weave_client_context
from weave.trace.init_message import check_min_trace_server_version
from weave.trace.refs import ObjectRef
from weave.trace_server_bindings import remote_http_trace_server
from weave.wandb_interface.auth import ApiKeyCredentials

TEST_SERVER_URL = "https://test.trace.server"
MIN_SERVER_VERSION = "1.0.0"


@pytest.mark.trace_server
@pytest.mark.parametrize("disabled_by", ["client_version", "server_version", "setting"])
def test_init_disabled_blocks_writes_and_can_reenable(monkeypatch, disabled_by):
    server_info = {
        "min_required_weave_python_version": "0.0.0",
        "trace_server_version": MIN_SERVER_VERSION,
    }
    if disabled_by == "client_version":
        server_info["min_required_weave_python_version"] = "999.0.0"
    elif disabled_by == "server_version":
        server_info["trace_server_version"] = "0.0.0"
    elif disabled_by == "setting":
        monkeypatch.setenv("WEAVE_DISABLED", "true")
    else:
        raise AssertionError(disabled_by)

    def respond(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/server_info":
            return httpx.Response(200, json=server_info)

        return httpx.Response(200, json={"digest": "test-digest"})

    transport = mock.Mock(wraps=respond)
    monkeypatch.setattr(
        remote_http_trace_server,
        "DefaultHttpxClient",
        lambda **kwargs: httpx.Client(transport=httpx.MockTransport(transport)),
    )
    monkeypatch.setenv("WF_TRACE_SERVER_URL", TEST_SERVER_URL)
    monkeypatch.setattr(weave_init, "MIN_TRACE_SERVER_VERSION", MIN_SERVER_VERSION)
    monkeypatch.setattr(
        weave_init, "get_wandb_auth_context", lambda: ApiKeyCredentials("test-key")
    )
    monkeypatch.setattr(weave_init, "get_username", lambda: "test-user")
    monkeypatch.setattr(weave_init, "_setup_conversation_tracing", lambda *args: None)
    monkeypatch.setattr(
        weave_init.init_message, "print_init_message", lambda *args, **kwargs: None
    )
    monkeypatch.setattr(
        remote_http_trace_server.project_creator,
        "ensure_project_exists",
        lambda *args: {"project_name": "test-project"},
    )
    monkeypatch.setattr(weave_client_context, "_global_weave_client", None)

    @weave.op
    def increment(value: int) -> int:
        return value + 1

    @weave.op
    async def increment_async(value: int) -> int:
        return value + 1

    try:
        client = weave.init("test-entity/test-project")
        monkeypatch.delenv("WEAVE_DISABLED", raising=False)
        transport.reset_mock()
        assert increment(2) == 3
        assert asyncio.run(increment_async(2)) == 3
        ref = weave.publish(
            Image.new("RGB", (1, 1)), name="image", tags=["test"], aliases=["test"]
        )
        assert ref == ObjectRef(
            entity="DISABLED", project="DISABLED", name="image", _digest="DISABLED"
        )
        client.flush()
        transport.assert_not_called()

        server_info["min_required_weave_python_version"] = "0.0.0"
        server_info["trace_server_version"] = MIN_SERVER_VERSION
        client = weave.init("test-entity/test-project")
        transport.reset_mock()
        assert increment(4) == 5
        assert asyncio.run(increment_async(4)) == 5
        client.flush()
        paths = {call.args[0].url.path for call in transport.call_args_list}
        assert paths == {
            "/obj/create",
            "/file/create",
            "/v2/test-entity/test-project/calls/complete",
        }
    finally:
        weave.finish()


class TestCheckMinTraceServerVersion:
    """Test check_min_trace_server_version with various client/server version combinations."""

    # Client has no requirement (MIN_TRACE_SERVER_VERSION = None)

    def test_client_none_server_none(self):
        """Client has no requirement, server doesn't report version -> compatible."""
        result = check_min_trace_server_version(
            trace_server_version=None,
            min_required_version=None,
            trace_server_url=TEST_SERVER_URL,
        )
        assert result is True

    def test_client_none_server_has_value(self):
        """Client has no requirement, server reports a version -> compatible."""
        result = check_min_trace_server_version(
            trace_server_version="1.0.0",
            min_required_version=None,
            trace_server_url=TEST_SERVER_URL,
        )
        assert result is True

    # Client has a requirement (MIN_TRACE_SERVER_VERSION = "0.5.0")

    def test_client_has_value_server_none(self):
        """Client requires version, server doesn't report -> incompatible."""
        result = check_min_trace_server_version(
            trace_server_version=None,
            min_required_version="0.5.0",
            trace_server_url=TEST_SERVER_URL,
        )
        assert result is False

    def test_client_has_value_server_too_low(self):
        """Client requires version, server version is too low -> incompatible."""
        result = check_min_trace_server_version(
            trace_server_version="0.3.0",
            min_required_version="0.5.0",
            trace_server_url=TEST_SERVER_URL,
        )
        assert result is False

    def test_client_has_value_server_exact_match(self):
        """Client requires version, server version matches exactly -> compatible."""
        result = check_min_trace_server_version(
            trace_server_version="0.5.0",
            min_required_version="0.5.0",
            trace_server_url=TEST_SERVER_URL,
        )
        assert result is True

    def test_client_has_value_server_higher(self):
        """Client requires version, server version exceeds requirement -> compatible."""
        result = check_min_trace_server_version(
            trace_server_version="1.0.0",
            min_required_version="0.5.0",
            trace_server_url=TEST_SERVER_URL,
        )
        assert result is True

    # Edge cases

    def test_prerelease_version_comparison(self):
        """Pre-release versions are lower than release versions."""
        # 0.5.0-dev0 < 0.5.0, so if client requires 0.5.0, server at 0.5.0-dev0 should fail
        result = check_min_trace_server_version(
            trace_server_version="0.5.0-dev0",
            min_required_version="0.5.0",
            trace_server_url=TEST_SERVER_URL,
        )
        assert result is False

    def test_prerelease_requirement_satisfied_by_release(self):
        """Release version satisfies pre-release requirement."""
        # 0.5.0 > 0.5.0-dev0, so server at 0.5.0 satisfies client requiring 0.5.0-dev0
        result = check_min_trace_server_version(
            trace_server_version="0.5.0",
            min_required_version="0.5.0-dev0",
            trace_server_url=TEST_SERVER_URL,
        )
        assert result is True
