import pytest
from pydantic import ValidationError

from weave.trace_server.agents.types import GenAIOTelExportReq
from weave.trace_server.sensitive_data.policy import SensitiveDataPolicy


def _request_payload() -> dict[str, object]:
    return {
        "processed_spans": [],
        "project_id": "entity/project",
        "wb_user_id": "user",
    }


def test_agent_sensitive_data_policy_defaults_off() -> None:
    request = GenAIOTelExportReq.model_validate(_request_payload())

    assert request.sensitive_data_policy is SensitiveDataPolicy.OFF


def test_agent_sensitive_data_policy_accepts_pii_v1() -> None:
    payload = _request_payload()
    payload["sensitive_data_policy"] = "pii-v1"

    request = GenAIOTelExportReq.model_validate(payload)

    assert request.sensitive_data_policy is SensitiveDataPolicy.PII_V1


def test_agent_sensitive_data_policy_rejects_null() -> None:
    payload = _request_payload()
    payload["sensitive_data_policy"] = None

    with pytest.raises(ValidationError):
        GenAIOTelExportReq.model_validate(payload)
