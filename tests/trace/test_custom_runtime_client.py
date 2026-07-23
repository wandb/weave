from unittest.mock import MagicMock

import weave
from weave.trace.weave_client import WeaveClient
from weave.trace_server import trace_server_interface as tsi
from weave.trace_server_bindings.client_interface import TraceServerClientInterface


def test_apply_custom_runtime_normalizes_string_and_explicit_runtime_ids() -> None:
    server = MagicMock(spec=TraceServerClientInterface)
    expected_result = tsi.CustomRuntimeApplyRes(
        name="support-agent",
        base_url="https://agent.example/v1",
        api_key_secret="AGENT_API_KEY",
        headers={"X-Tenant-ID": "customer-1"},
        runtime_ids=[
            tsi.CustomRuntimeIDRes(
                id="support-v12",
                max_tokens=4096,
                playground_id="custom::support-agent::support-v12",
            ),
            tsi.CustomRuntimeIDRes(
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

    result = client.apply_custom_runtime(
        name="support-agent",
        base_url="https://agent.example/v1",
        api_key_secret="AGENT_API_KEY",
        headers={"X-Tenant-ID": "customer-1"},
        runtime_ids=[
            "support-v12",
            tsi.CustomRuntimeID(id="support-canary", max_tokens=8192),
        ],
    )

    server.custom_runtime_apply.assert_called_once_with(
        tsi.CustomRuntimeApplyReq(
            project_id="entity/project",
            runtime_name="support-agent",
            base_url="https://agent.example/v1",
            api_key_secret="AGENT_API_KEY",
            headers={"X-Tenant-ID": "customer-1"},
            runtime_ids=[
                tsi.CustomRuntimeID(id="support-v12", max_tokens=4096),
                tsi.CustomRuntimeID(id="support-canary", max_tokens=8192),
            ],
        )
    )
    assert result == expected_result


def test_custom_runtime_id_is_part_of_public_weave_api() -> None:
    assert weave.CustomRuntimeID is tsi.CustomRuntimeID
