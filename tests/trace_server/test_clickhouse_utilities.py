import json
import math
from unittest.mock import MagicMock, patch

import pytest

from weave.trace_server import clickhouse_trace_server_batched as chts
from weave.trace_server.clickhouse.utilities import (
    any_dump_to_any,
    any_value_to_dump,
    dict_dump_to_dict,
    dict_value_to_dump,
    sanitize_invalid_utf8_surrogates,
)


def test_sanitize_invalid_utf8_surrogates_replaces_lone_surrogates() -> None:
    # Covers malformed strings exactly as Python receives them after JSON
    # decoding, while ensuring valid surrogate pairs and real emoji survive.
    value = {
        "bad": "broken \ud83d",
        "pair": "\ud83d\ude00",
        "emoji": "\U0001f600",
        "items": ["nested \udc00"],
    }

    sanitized = sanitize_invalid_utf8_surrogates(value)

    assert sanitized == {
        "bad": "broken \ufffd",
        "pair": "\U0001f600",
        "emoji": "\U0001f600",
        "items": ["nested \ufffd"],
    }
    str(sanitized).encode("utf-8")


def test_insert_does_not_sanitize_successful_clean_clickhouse_write() -> None:
    # Clean inserts should stay on the old hot path: no recursive sanitation
    # unless clickhouse_connect first reports an encoding failure.
    data = [["valid \U0001f600"]]
    mock_ch_client = MagicMock()
    mock_ch_client.insert.return_value = MagicMock()

    with patch.object(
        chts.ClickHouseTraceServer, "_mint_client", return_value=mock_ch_client
    ):
        server = chts.ClickHouseTraceServer(host="test_host")
        server._insert(
            "call_parts",
            data=data,
            column_names=["valid"],
        )

    inserted_data = mock_ch_client.insert.call_args.kwargs["data"]
    assert inserted_data is data


def test_insert_sanitizes_invalid_utf8_surrogates_after_encode_error() -> None:
    # Direct string columns like `exception` or `display_name` bypass JSON dumps,
    # so a UnicodeEncodeError should trigger one sanitized retry of the same batch.
    mock_ch_client = MagicMock()
    mock_ch_client.insert.side_effect = [
        UnicodeEncodeError("utf-8", "broken \ud83d", 7, 8, "surrogates not allowed"),
        MagicMock(),
    ]

    with patch.object(
        chts.ClickHouseTraceServer, "_mint_client", return_value=mock_ch_client
    ):
        server = chts.ClickHouseTraceServer(host="test_host")
        server._insert(
            "call_parts",
            data=[["valid \U0001f600", "broken \ud83d"]],
            column_names=["valid", "broken"],
        )

    first_insert = mock_ch_client.insert.call_args_list[0].kwargs["data"]
    retried_insert = mock_ch_client.insert.call_args_list[1].kwargs["data"]
    assert first_insert == [["valid \U0001f600", "broken \ud83d"]]
    assert retried_insert is not first_insert
    inserted_data = retried_insert
    assert inserted_data == [["valid \U0001f600", "broken \ufffd"]]
    str(inserted_data).encode("utf-8")


def test_dict_value_to_dump_round_trip() -> None:
    value = {"a": 1, "b": [1, 2, {"c": "x"}], "d": None, "e": True}
    assert dict_dump_to_dict(dict_value_to_dump(value)) == value


def test_any_value_to_dump_round_trip() -> None:
    for value in ({"a": 1}, [1, 2, 3], "hello", 42, 3.14, True, None):
        assert any_dump_to_any(any_value_to_dump(value)) == value


def test_dict_value_to_dump_rejects_non_dict() -> None:
    with pytest.raises(TypeError):
        dict_value_to_dump([1, 2, 3])  # type: ignore[arg-type]


def test_dict_dump_to_dict_rejects_non_object_payload() -> None:
    with pytest.raises(TypeError):
        dict_dump_to_dict("[1, 2, 3]")


def test_non_string_dict_keys_are_coerced() -> None:
    # orjson with OPT_NON_STR_KEYS coerces int keys to str, matching stdlib json.dumps.
    out = dict_value_to_dump({1: "x", 2: "y"})
    assert json.loads(out) == {"1": "x", "2": "y"}


def test_nan_and_inf_serialize_to_null() -> None:
    # orjson emits null for NaN/Inf (strict JSON). This is a deliberate change from
    # stdlib json's NaN/Infinity literals -> ClickHouse JSONExtract* now works on
    # these columns.
    assert any_value_to_dump(math.nan) == "null"
    assert any_value_to_dump(math.inf) == "null"
    assert any_value_to_dump(-math.inf) == "null"


def test_legacy_nan_literal_payload_still_loads() -> None:
    # Pre-orjson rows stored as `{"x": NaN}` must still round-trip through reads.
    # Stdlib json.loads accepts these; orjson does not -> we fall back on
    # JSONDecodeError.
    legacy = json.dumps({"x": float("nan"), "y": float("inf")})
    loaded = dict_dump_to_dict(legacy)
    assert math.isnan(loaded["x"])
    assert loaded["y"] == float("inf")
