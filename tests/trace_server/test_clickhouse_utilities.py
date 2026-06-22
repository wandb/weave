from unittest.mock import MagicMock, patch

from clickhouse_connect import common as ch_common
from clickhouse_connect.driver.httpclient import HttpClient

from weave.trace_server import clickhouse_trace_server_batched as chts
from weave.trace_server import clickhouse_trace_server_settings as ch_settings
from weave.trace_server.clickhouse.utilities import sanitize_invalid_utf8_surrogates


def test_poisoned_client_settings_are_sent_not_rejected() -> None:
    # A client minted during a CH degradation window caches an empty/readonly
    # server_settings map; 'send' lets the rejected weave settings reach the server.
    assert ch_common.get_setting("invalid_setting_action") == "send"

    poisoned = HttpClient.__new__(HttpClient)
    poisoned.server_settings = {}
    poisoned.optional_transport_settings = set()

    settings = {
        **ch_settings.CLICKHOUSE_DEFAULT_QUERY_SETTINGS,
        **ch_settings.CLICKHOUSE_ASYNC_INSERT_SETTINGS,
    }
    validated = poisoned._validate_settings(settings)

    assert validated == settings


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
