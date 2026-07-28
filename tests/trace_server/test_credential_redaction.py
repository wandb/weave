"""Credential redaction at ingest: the name policy, the walk, and the hook.

Unit coverage for `weave.trace_server.credential_redaction`, a converter-level
check that every producer of the client-authored call columns applies it, and one
end-to-end insert that reads the stored columns back out of ClickHouse.
"""

from __future__ import annotations

import datetime
import json
import uuid
from typing import Any

import pytest

from tests.trace.util import NOT_CLICKHOUSE_BACKEND
from tests.trace_server.conftest_lib.trace_server_external_adapter import b64
from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.clickhouse.schema_converters import (
    complete_call_to_ch_insertable,
    start_call_for_insert_to_ch_insertable,
    start_end_calls_to_ch_complete_insertable,
)
from weave.trace_server.clickhouse_schema import CallCHInsertable
from weave.trace_server.clickhouse_trace_server_batched import ClickHouseTraceServer
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
    ("key", "normalized"),
    [
        ("apiKey", "apikey"),
        ("api_key", "apikey"),
        ("API_KEY", "apikey"),
        ("x-api-key", "xapikey"),
    ],
)
def test_every_spelling_of_a_name_is_redacted(key: str, normalized: str) -> None:
    # One field is spelled four ways across SDKs, so the policy matches on the
    # name with case and separators normalized away.
    redacted, tally = redact_sensitive_keys({key: PLACEHOLDER})

    assert redacted == {key: REDACTED_VALUE}
    assert tally == {normalized: 1}


@pytest.mark.parametrize(
    ("key", "normalized"),
    [
        ("aws_secret_access_key", "awssecretaccesskey"),
        ("openai_api_key", "openaiapikey"),
        ("api_token", "apitoken"),
        ("vertex_credentials", "vertexcredentials"),
    ],
)
def test_vendor_prefixed_names_are_redacted(key: str, normalized: str) -> None:
    # The `<vendor>_<credential>` family is open-ended, so it is matched by
    # suffix instead of one literal per vendor.
    redacted, tally = redact_sensitive_keys({key: PLACEHOLDER})

    assert redacted == {key: REDACTED_VALUE}
    assert tally == {normalized: 1}


@pytest.mark.parametrize(
    "key",
    [
        # Ordinary words: real datasets carry these as columns.
        "token",
        "secret",
        "password",
        "credentials",
        # Substring matching would hit these; suffix matching does not.
        "monkey",
        "keyboard",
        "keywords",
        "client_secret_name",
        # Neighbours of a redacted field that are not themselves credentials.
        "baseURL",
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
        "items": [{"label": "first"}, {"authorization": PLACEHOLDER}],
    }

    redacted, tally = redact_sensitive_keys(payload)

    assert redacted == {
        "endpoint": "https://service.example.com/v1",
        "options": {"apiKey": REDACTED_VALUE, "retries": 2},
        "items": [{"label": "first"}, {"authorization": REDACTED_VALUE}],
    }
    assert tally == {"apikey": 1, "authorization": 1}


def test_only_non_empty_strings_are_replaced() -> None:
    payload = {
        # A tool schema *describes* a credential field; the value is a dict.
        "tools": [{"properties": {"apiKey": {"type": "string"}}}],
        # `has_api_key` matches the policy by suffix, but the value is a flag.
        "has_api_key": True,
        "api_key": 1234,
        "authToken": None,
        "x-api-key": "",
    }

    redacted, tally = redact_sensitive_keys(payload)

    assert redacted is payload
    assert tally == {}


def test_token_is_deliberately_outside_the_policy() -> None:
    # `token` is a normal dataset column for tokenization and NER, so adding it
    # to the policy would destroy that data. This test fails if anyone does.
    payload = {
        "logprobs": [{"token": "running", "logprob": -0.1}],
        "labels": [{"token": "Ada", "label": "B-PER"}],
    }

    redacted, tally = redact_sensitive_keys(payload)

    assert redacted is payload
    assert tally == {}


def test_credential_inside_a_tuple_is_replaced() -> None:
    # `json.dumps` writes a tuple as an array, so a tuple is a real path into
    # the stored column.
    payload = {"args": ({"apiKey": PLACEHOLDER},)}

    redacted, tally = redact_sensitive_keys(payload)

    assert redacted == {"args": ({"apiKey": REDACTED_VALUE},)}
    assert json.loads(json.dumps(redacted)) == {"args": [{"apiKey": REDACTED_VALUE}]}
    assert tally == {"apikey": 1}


def test_non_string_keys_do_not_break_the_walk() -> None:
    payload: dict[Any, Any] = {7: {"apiKey": PLACEHOLDER}, None: "kept"}

    redacted, tally = redact_sensitive_keys(payload)

    assert redacted == {7: {"apiKey": REDACTED_VALUE}, None: "kept"}
    assert tally == {"apikey": 1}


def test_credential_five_levels_down_is_replaced() -> None:
    payload = {"a": [{"b": {"c": [{"authorization": PLACEHOLDER}]}}]}

    redacted, tally = redact_sensitive_keys(payload)

    assert redacted == {"a": [{"b": {"c": [{"authorization": REDACTED_VALUE}]}}]}
    assert tally == {"authorization": 1}


def test_tally_counts_every_hit_per_normalized_name() -> None:
    payload = {
        "apiKey": PLACEHOLDER,
        "nested": {"api_key": PLACEHOLDER, "authToken": PLACEHOLDER},
    }

    _, tally = redact_sensitive_keys(payload)

    assert tally == {"apikey": 2, "authtoken": 1}


# ---------------------------------------------------------------------------
# Copy-on-write
# ---------------------------------------------------------------------------


def test_clean_payload_comes_back_by_identity() -> None:
    payload = {"model": "a-model", "messages": [{"role": "user", "content": "hi"}]}

    redacted, tally = redact_sensitive_keys(payload)

    assert redacted is payload
    assert tally == {}


def test_source_payload_is_not_mutated_and_clean_subtrees_are_shared() -> None:
    payload = {
        "options": {"apiKey": PLACEHOLDER, "baseURL": "https://service.example.com"},
        "message": {"role": "user", "content": "hi"},
    }

    redacted, _ = redact_sensitive_keys(payload)

    assert payload == {
        "options": {"apiKey": PLACEHOLDER, "baseURL": "https://service.example.com"},
        "message": {"role": "user", "content": "hi"},
    }
    assert redacted["message"] is payload["message"]
    assert redacted["options"] == {
        "apiKey": REDACTED_VALUE,
        "baseURL": "https://service.example.com",
    }


def test_second_pass_neither_copies_nor_counts_again() -> None:
    # Identity on the second pass is what makes the walk idempotent.
    redacted, _ = redact_sensitive_keys({"options": {"apiKey": PLACEHOLDER}})

    again, tally = redact_sensitive_keys(redacted)

    assert again is redacted
    assert tally == {}


def test_eval_dataset_row_keeps_its_serialization() -> None:
    # Eval-result rows are grouped by a SHA256 of the raw JSON under
    # `inputs.example`, so a row the policy does not name must serialize
    # byte for byte as before.
    example = {"question": "capital of France?", "answer": "Paris", "id": "row-1"}
    payload = {"example": example, "model": "a-model"}

    redacted, _ = redact_sensitive_keys(payload)

    assert redacted is payload
    assert json.dumps(redacted["example"]) == json.dumps(example)


# ---------------------------------------------------------------------------
# The hook: every producer of the client-authored call columns
# ---------------------------------------------------------------------------

_STARTED_AT = datetime.datetime(2026, 1, 1, tzinfo=datetime.timezone.utc)
_ENDED_AT = _STARTED_AT + datetime.timedelta(seconds=1)

_INPUTS = {"options": {"authorization": PLACEHOLDER}}
_ATTRIBUTES = {"options": {"apiKey": PLACEHOLDER}}
_REDACTED_INPUTS = {"options": {"authorization": REDACTED_VALUE}}
_REDACTED_ATTRIBUTES = {"options": {"apiKey": REDACTED_VALUE}}


def _convert_start() -> CallCHInsertable:
    return start_call_for_insert_to_ch_insertable(
        tsi.StartedCallSchemaForInsert(
            project_id=PROJECT_ID,
            id=str(uuid.uuid4()),
            trace_id=str(uuid.uuid4()),
            op_name="op",
            started_at=_STARTED_AT,
            attributes=_ATTRIBUTES,
            inputs=_INPUTS,
        ),
        retention_days=0,
    )


def _convert_start_end() -> CallCHInsertable:
    call_id = str(uuid.uuid4())
    return start_end_calls_to_ch_complete_insertable(
        tsi.StartedCallSchemaForInsert(
            project_id=PROJECT_ID,
            id=call_id,
            trace_id=str(uuid.uuid4()),
            op_name="op",
            started_at=_STARTED_AT,
            attributes=_ATTRIBUTES,
            inputs=_INPUTS,
        ),
        tsi.EndedCallSchemaForInsert(
            project_id=PROJECT_ID,
            id=call_id,
            ended_at=_ENDED_AT,
            output={},
            summary={},
        ),
        retention_days=0,
    )


def _convert_complete() -> CallCHInsertable:
    return complete_call_to_ch_insertable(
        tsi.CompletedCallSchemaForInsert(
            project_id=PROJECT_ID,
            id=str(uuid.uuid4()),
            trace_id=str(uuid.uuid4()),
            op_name="op",
            started_at=_STARTED_AT,
            ended_at=_ENDED_AT,
            attributes=_ATTRIBUTES,
            inputs=_INPUTS,
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
def test_converters_redact_both_client_authored_columns(convert: Any) -> None:
    # The hook lives inside the converters, so any caller inherits it.
    row = convert()

    assert json.loads(row.inputs_dump) == _REDACTED_INPUTS
    assert json.loads(row.attributes_dump) == _REDACTED_ATTRIBUTES


# ---------------------------------------------------------------------------
# End to end through the batch ingest path
# ---------------------------------------------------------------------------


@pytest.fixture
def batch_server(trace_server):
    """The ClickHouse server underneath the fixture, routing to `call_parts`."""
    server = trace_server._internal_trace_server
    assert isinstance(server, ClickHouseTraceServer)
    server.table_routing_resolver._mode = CallsStorageServerMode.AUTO
    return server


@pytest.mark.skipif(
    NOT_CLICKHOUSE_BACKEND, reason="ClickHouse-only: raw call column reads"
)
def test_call_start_batch_stores_redacted_columns(batch_server) -> None:
    """A batched call start persists the redacted columns and reads back redacted.

    The external adapter does not wrap `call_start_batch`, so this hits the
    internal server directly with a pre-encoded project id.
    """
    internal_project_id = b64(f"{TEST_ENTITY}/batch_{uuid.uuid4().hex[:8]}")
    call_id = str(uuid.uuid4())

    batch_server.call_start_batch(
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
                            attributes=_ATTRIBUTES,
                            inputs=_INPUTS,
                        )
                    ),
                ),
            ]
        )
    )

    row = batch_server.ch_client.query(
        "SELECT inputs_dump, attributes_dump FROM call_parts "
        "WHERE project_id = {project_id:String} AND id = {call_id:String}",
        parameters={"project_id": internal_project_id, "call_id": call_id},
    ).result_rows
    assert len(row) == 1
    assert json.loads(row[0][0]) == _REDACTED_INPUTS
    assert json.loads(row[0][1]) == _REDACTED_ATTRIBUTES

    call = batch_server.call_read(
        tsi.CallReadReq(project_id=internal_project_id, id=call_id)
    ).call
    assert call is not None
    assert call.inputs == _REDACTED_INPUTS
    assert call.attributes == _REDACTED_ATTRIBUTES
