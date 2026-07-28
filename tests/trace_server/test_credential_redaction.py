"""Credential redaction at ingest: the name policy, the walk, and the hook.

Unit coverage for `weave.trace_server.credential_redaction`, a converter-level
check that every producer of the client-authored call columns applies it, and one
end-to-end insert that reads the stored columns back out of ClickHouse.
"""

from __future__ import annotations

import datetime
import json
import uuid
from collections.abc import Callable
from typing import Any

import pytest

from tests.trace_server.conftest_lib.trace_server_external_adapter import b64
from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.clickhouse.schema_converters import (
    complete_call_to_ch_insertable,
    start_call_for_insert_to_ch_insertable,
    start_end_calls_to_ch_complete_insertable,
)
from weave.trace_server.clickhouse_schema import (
    CallCompleteCHInsertable,
    CallStartCHInsertable,
)
from weave.trace_server.credential_redaction import (
    REDACTED_VALUE,
    redact_sensitive_keys,
    should_redact,
)
from weave.trace_server.project_version.types import CallsStorageServerMode

# A neutral stand-in for whatever a client actually put in the field.
PLACEHOLDER = "value-to-redact"

TEST_ENTITY = "redaction_entity"

# The converters validate that the project id is already internal (base64).
PROJECT_ID = b64(f"{TEST_ENTITY}/project")

# ---------------------------------------------------------------------------
# The name policy
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "key",
    [
        # One field, four spellings across SDKs: normalization collapses them.
        "apiKey",
        "api_key",
        "API_KEY",
        "x-api-key",
        # One per suffix entry, each spelled so only the suffix can match it.
        "service_access_token",
        "openai_api_key",
        "replicate_api_token",
        "azure_client_secret",
        "service_private_key",
        "oauth_refresh_token",
        "aws_secret_access_key",
        "service_secret_key",
        "aws_session_token",
        # One per exact entry: names no suffix reaches.
        "auth_headers",
        "authorization",
        "auth_token",
        "aws_access_key",
        "aws_access_key_id",
        "bearer_token",
        "vertex_credentials",
        "webhook_key",
        "webhook_secret",
    ],
)
def test_credential_names_are_redacted(key: str) -> None:
    # Every policy entry has a case here, so the policy cannot silently shrink.
    assert redact_sensitive_keys({key: PLACEHOLDER}) == {key: REDACTED_VALUE}


@pytest.mark.parametrize(
    "key",
    [
        # Ordinary words, excluded because they occur as dataset columns.
        "token",
        "secret",
        "password",
        "credentials",
        # Substring matching would hit these; suffix matching does not.
        "monkey",
        "keyboard",
        "keywords",
        "client_secret_name",
        # Ordinary configuration field names.
        "endpoint",
        "model",
    ],
)
def test_names_outside_the_policy_are_left_alone(key: str) -> None:
    assert not should_redact(key)


def test_over_length_name_still_matches_the_policy() -> None:
    # Names too long to memoize take the uncached path, not a free pass.
    assert should_redact("x" * 70 + "_api_key")


# ---------------------------------------------------------------------------
# The walk
# ---------------------------------------------------------------------------


def test_nested_credentials_are_replaced_and_the_rest_is_kept() -> None:
    payload = {
        "endpoint": "https://service.example.com/v1",
        "options": {"apiKey": PLACEHOLDER, "retries": 2},
        "items": [{"label": "first"}, {"deep": {"authorization": PLACEHOLDER}}],
    }

    assert redact_sensitive_keys(payload) == {
        "endpoint": "https://service.example.com/v1",
        "options": {"apiKey": REDACTED_VALUE, "retries": 2},
        "items": [{"label": "first"}, {"deep": {"authorization": REDACTED_VALUE}}],
    }


def test_only_non_empty_strings_are_replaced() -> None:
    payload = {
        # A tool schema *describes* a credential field; the value is a dict.
        "tools": [{"properties": {"apiKey": {"type": "string"}}}],
        # `has_api_key` matches the policy by suffix, but the value is a flag.
        "has_api_key": True,
        # Descending into a matched name would overwrite the schema's own
        # `"string"` above, which is the corruption this rule prevents.
        "authorization": ["read", "write"],
        "api_key": 1234,
        "authToken": None,
        "x-api-key": "",
    }

    assert redact_sensitive_keys(payload) is payload


def test_dataset_columns_are_not_treated_as_credentials() -> None:
    # Redaction is irreversible, so names that occur as legitimate dataset
    # columns stay out of the policy. These two shapes are why.
    payload = {
        "logprobs": [{"token": "running", "logprob": -0.1}],
        "labels": [{"token": "Ada", "label": "B-PER"}],
    }

    assert redact_sensitive_keys(payload) is payload


def test_credential_inside_a_tuple_is_replaced() -> None:
    # `json.dumps` writes a tuple as an array, so a tuple is a real path into
    # the stored column.
    redacted = redact_sensitive_keys({"args": ({"apiKey": PLACEHOLDER},)})

    assert redacted == {"args": ({"apiKey": REDACTED_VALUE},)}
    assert json.loads(json.dumps(redacted)) == {"args": [{"apiKey": REDACTED_VALUE}]}


def test_non_string_keys_do_not_break_the_walk() -> None:
    payload: dict[Any, Any] = {7: {"apiKey": PLACEHOLDER}, None: "kept"}

    assert redact_sensitive_keys(payload) == {
        7: {"apiKey": REDACTED_VALUE},
        None: "kept",
    }


# ---------------------------------------------------------------------------
# Copy-on-write
# ---------------------------------------------------------------------------


def test_clean_payload_comes_back_by_identity() -> None:
    payload = {"model": "a-model", "messages": [{"role": "user", "content": "hi"}]}

    assert redact_sensitive_keys(payload) is payload


def test_source_payload_is_not_mutated_and_clean_subtrees_are_shared() -> None:
    payload = {
        "options": {"apiKey": PLACEHOLDER, "endpoint": "https://service.example.com"},
        "message": {"role": "user", "content": "hi"},
    }

    redacted = redact_sensitive_keys(payload)

    assert payload == {
        "options": {"apiKey": PLACEHOLDER, "endpoint": "https://service.example.com"},
        "message": {"role": "user", "content": "hi"},
    }
    assert redacted["message"] is payload["message"]
    assert redacted["options"] == {
        "apiKey": REDACTED_VALUE,
        "endpoint": "https://service.example.com",
    }


def test_value_the_client_already_redacted_is_left_alone() -> None:
    # The Python client redacts `api_key`, `auth_headers` and `authorization`
    # before sending, so those arrive already holding the marker. Returning them
    # by identity keeps the walk from copying every such payload, and makes it
    # idempotent.
    payload = {"options": {"api_key": REDACTED_VALUE}}

    assert redact_sensitive_keys(payload) is payload


def test_eval_dataset_row_keeps_its_identity_when_a_sibling_is_redacted() -> None:
    # Eval-result rows are grouped by a SHA256 of the raw JSON under
    # `inputs.example`. Redacting elsewhere in the payload must leave that
    # subtree byte-identical, or rows regroup and distinct rows collapse.
    example = {"question": "capital of France?", "answer": "Paris", "id": "row-1"}
    payload = {"example": example, "options": {"apiKey": PLACEHOLDER}}

    redacted = redact_sensitive_keys(payload)

    assert redacted is not payload
    assert redacted["example"] is example


# ---------------------------------------------------------------------------
# The hook: every ClickHouse producer of the client-authored call columns
# ---------------------------------------------------------------------------

_STARTED_AT = datetime.datetime(2026, 1, 1, tzinfo=datetime.timezone.utc)
_ENDED_AT = _STARTED_AT + datetime.timedelta(seconds=1)

_REDACTED_INPUTS = {"options": {"authorization": REDACTED_VALUE}}
_REDACTED_ATTRIBUTES = {"options": {"apiKey": REDACTED_VALUE}}


def _inputs() -> dict[str, Any]:
    # Built fresh per call: a shared payload would let one case pre-redact the
    # next one's fixture and hide a missing hook.
    return {"options": {"authorization": PLACEHOLDER}}


def _attributes() -> dict[str, Any]:
    return {"options": {"apiKey": PLACEHOLDER}}


def _started_call(call_id: str) -> tsi.StartedCallSchemaForInsert:
    return tsi.StartedCallSchemaForInsert(
        project_id=PROJECT_ID,
        id=call_id,
        trace_id=str(uuid.uuid4()),
        op_name="op",
        started_at=_STARTED_AT,
        attributes=_attributes(),
        inputs=_inputs(),
    )


def _convert_start() -> CallStartCHInsertable:
    return start_call_for_insert_to_ch_insertable(
        _started_call(str(uuid.uuid4())), retention_days=0
    )


def _convert_start_end() -> CallCompleteCHInsertable:
    call_id = str(uuid.uuid4())
    return start_end_calls_to_ch_complete_insertable(
        _started_call(call_id),
        tsi.EndedCallSchemaForInsert(
            project_id=PROJECT_ID,
            id=call_id,
            ended_at=_ENDED_AT,
            output={},
            summary={},
        ),
        retention_days=0,
    )


def _convert_complete() -> CallCompleteCHInsertable:
    return complete_call_to_ch_insertable(
        tsi.CompletedCallSchemaForInsert(
            project_id=PROJECT_ID,
            id=str(uuid.uuid4()),
            trace_id=str(uuid.uuid4()),
            op_name="op",
            started_at=_STARTED_AT,
            ended_at=_ENDED_AT,
            attributes=_attributes(),
            inputs=_inputs(),
            output={},
            summary={},
        ),
        retention_days=0,
    )


@pytest.mark.parametrize(
    "convert",
    [_convert_start, _convert_start_end, _convert_complete],
    ids=["call_start", "start_end_complete", "complete"],
)
def test_converters_redact_both_client_authored_columns(
    convert: Callable[[], CallStartCHInsertable | CallCompleteCHInsertable],
) -> None:
    # The hook lives inside the converters, so any caller inherits it.
    row = convert()

    assert json.loads(row.inputs_dump) == _REDACTED_INPUTS
    assert json.loads(row.attributes_dump) == _REDACTED_ATTRIBUTES


# ---------------------------------------------------------------------------
# End to end through the batch ingest path
# ---------------------------------------------------------------------------


@pytest.fixture
def auto_routed_ch_server(ch_server):
    """The ClickHouse server under AUTO routing, as in `test_ttl_insert_paths.py`."""
    ch_server.table_routing_resolver._mode = CallsStorageServerMode.AUTO
    return ch_server


def test_call_start_batch_stores_redacted_columns(auto_routed_ch_server) -> None:
    """A batched call start persists redacted columns and reads back redacted.

    The external adapter does not wrap `call_start_batch`, so this hits the
    internal server directly with a pre-encoded project id.
    """
    internal_project_id = b64(f"{TEST_ENTITY}/batch_{uuid.uuid4().hex[:8]}")
    call_id = str(uuid.uuid4())

    auto_routed_ch_server.call_start_batch(
        tsi.CallCreateBatchReq(
            batch=[
                tsi.CallBatchStartMode(
                    req=tsi.CallStartReq(
                        start=tsi.StartedCallSchemaForInsert(
                            project_id=internal_project_id,
                            id=call_id,
                            trace_id=str(uuid.uuid4()),
                            op_name="op",
                            started_at=_STARTED_AT,
                            attributes=_attributes(),
                            inputs=_inputs(),
                        )
                    ),
                ),
            ]
        )
    )

    row = auto_routed_ch_server.ch_client.query(
        "SELECT inputs_dump, attributes_dump FROM call_parts "
        "WHERE project_id = {project_id:String} AND id = {call_id:String}",
        parameters={"project_id": internal_project_id, "call_id": call_id},
    ).result_rows
    assert len(row) == 1
    assert json.loads(row[0][0]) == _REDACTED_INPUTS
    assert json.loads(row[0][1]) == _REDACTED_ATTRIBUTES


def _write_via_call_start(server: Any, project_id: str, call_id: str) -> None:
    server.call_start(
        tsi.CallStartReq(
            start=tsi.StartedCallSchemaForInsert(
                project_id=project_id,
                id=call_id,
                trace_id=str(uuid.uuid4()),
                op_name="op",
                started_at=_STARTED_AT,
                attributes=_attributes(),
                inputs=_inputs(),
            )
        )
    )


def _write_via_calls_complete(server: Any, project_id: str, call_id: str) -> None:
    server.calls_complete(
        tsi.CallsUpsertCompleteReq(
            batch=[
                tsi.CompletedCallSchemaForInsert(
                    project_id=project_id,
                    id=call_id,
                    trace_id=str(uuid.uuid4()),
                    op_name="op",
                    started_at=_STARTED_AT,
                    ended_at=_ENDED_AT,
                    attributes=_attributes(),
                    inputs=_inputs(),
                    output=None,
                    summary={"usage": {}, "status_counts": {}},
                )
            ]
        )
    )


@pytest.mark.parametrize(
    "write",
    [_write_via_call_start, _write_via_calls_complete],
    ids=["call_start", "calls_complete"],
)
def test_call_read_returns_redacted_inputs_and_attributes(trace_server, write) -> None:
    """Read-back is redacted on either backend, for both write paths.

    The in-memory backend hooks `call_start` and `calls_complete` separately, so
    both need covering or one could silently stop matching ClickHouse.
    """
    project_id = f"{TEST_ENTITY}/read_{uuid.uuid4().hex[:8]}"
    call_id = str(uuid.uuid4())

    write(trace_server, project_id, call_id)

    call = trace_server.call_read(
        tsi.CallReadReq(project_id=project_id, id=call_id)
    ).call
    assert call is not None
    assert call.inputs == _REDACTED_INPUTS
    assert call.attributes == _REDACTED_ATTRIBUTES
