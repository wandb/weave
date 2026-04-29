import json
from unittest.mock import MagicMock, patch

from weave.trace_server import clickhouse_trace_server_batched as chts
from weave.trace_server.clickhouse.utilities import (
    any_value_to_dump,
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


def test_dump_helpers_sanitize_invalid_utf8_surrogates() -> None:
    # JSON dump columns are usually safe because `json.dumps` escapes strings,
    # but sanitizing here prevents invalid Unicode from round-tripping back out.
    dumped_dict = dict_value_to_dump({"bad": "broken \ud83d"})
    dumped_any = any_value_to_dump(["nested \udc00"])

    assert json.loads(dumped_dict) == {"bad": "broken \ufffd"}
    assert json.loads(dumped_any) == ["nested \ufffd"]
    dumped_dict.encode("utf-8")
    dumped_any.encode("utf-8")


def test_insert_sanitizes_invalid_utf8_surrogates_before_clickhouse() -> None:
    # Direct string columns like `exception` or `display_name` bypass JSON dumps,
    # so the final insert path must normalize rows before clickhouse_connect.
    mock_ch_client = MagicMock()
    mock_ch_client.insert.return_value = MagicMock()

    with patch.object(
        chts.ClickHouseTraceServer, "_mint_client", return_value=mock_ch_client
    ):
        server = chts.ClickHouseTraceServer(host="test_host")
        server._insert(
            "call_parts",
            data=[["valid \U0001f600", "broken \ud83d"]],
            column_names=["valid", "broken"],
        )

    inserted_data = mock_ch_client.insert.call_args.kwargs["data"]
    assert inserted_data == [["valid \U0001f600", "broken \ufffd"]]
    str(inserted_data).encode("utf-8")
