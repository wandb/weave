from unittest.mock import MagicMock

import weave
from weave.trace.weave_client import WeaveClient
from weave.trace_server_bindings.client_interface import TraceServerClientInterface
from weave.vendor.weave_server_sdk.types import V2RuntimeApplyResponse
from weave.vendor.weave_server_sdk.types.v2_runtime_apply_response import RuntimeID


def test_register_custom_runtime_normalizes_string_and_explicit_runtime_ids() -> None:
    server = MagicMock(spec=TraceServerClientInterface)
    expected_result = V2RuntimeApplyResponse(
        name="support-agent",
        base_url="https://agent.example/v1",
        api_key_secret="AGENT_API_KEY",
        headers={"X-Tenant-ID": "customer-1"},
        runtime_ids=[
            RuntimeID(
                id="support-v12",
                max_tokens=4096,
                playground_id="custom::support-agent::support-v12",
            ),
            RuntimeID(
                id="support-canary",
                max_tokens=8192,
                playground_id="custom::support-agent::support-canary",
            ),
        ],
    )
    server.custom_runtime_apply.return_value = expected_result
    client = WeaveClient(
        "entity",
        "project",
        server,
        ensure_project_exists=False,
    )

    result = client.register_custom_runtime(
        name="support-agent",
        base_url="https://agent.example/v1",
        api_key_secret="AGENT_API_KEY",
        headers={"X-Tenant-ID": "customer-1"},
        runtime_ids=[
            "support-v12",
            weave.CustomRuntimeID(id="support-canary", max_tokens=8192),
        ],
    )

    server.custom_runtime_apply.assert_called_once_with(
        {
            "project_id": "entity/project",
            "runtime_name": "support-agent",
            "base_url": "https://agent.example/v1",
            "api_key_secret": "AGENT_API_KEY",
            "headers": {"X-Tenant-ID": "customer-1"},
            "runtime_ids": [
                {"id": "support-v12", "max_tokens": 4096},
                {"id": "support-canary", "max_tokens": 8192},
            ],
        }
    )
    assert result == expected_result
