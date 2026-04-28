from collections import deque
from typing import Any

from clickhouse_connect.driver.exceptions import StreamCompleteException
from clickhouse_connect.driver.httpclient import HttpClient
from clickhouse_connect.driver.query import QueryContext, QueryResult
from clickhouse_connect.driver.transform import NativeTransform
from clickhouse_connect.driver.types import ByteSource


class _DummyHTTPResponse:
    def __init__(self) -> None:
        self.headers: dict[str, str] = {}


class _RecordingTransform:
    def parse_response(self, byte_source: Any, context: QueryContext) -> QueryResult:
        return QueryResult([])


class _RecordingHttpClient:
    database = None
    protocol_version = None
    compression = False
    _send_comp_setting = False
    form_encode_query_params = False
    query_retries = 0
    _rename_response_column = None
    _transform = _RecordingTransform()

    def __init__(self) -> None:
        self.server_wait_values: list[bool] = []

    def _validate_settings(self, settings: dict[str, Any]) -> dict[str, Any]:
        return {}

    def _prep_query(self, context: QueryContext) -> str | bytes:
        return context.final_query

    def _raw_request(
        self,
        data: str | bytes,
        params: dict[str, str],
        headers: dict[str, Any],
        *,
        stream: bool,
        retries: int,
        fields: dict[str, tuple] | None,
        server_wait: bool,
    ) -> _DummyHTTPResponse:
        self.server_wait_values.append(server_wait)
        return _DummyHTTPResponse()

    def _check_tz_change(self, timezone: str | None) -> None:
        return None

    def _summary(self, response: _DummyHTTPResponse) -> dict[str, Any]:
        return {}


class _ScriptedNativeSource(ByteSource):
    def __init__(
        self,
        leb128_values: list[int] | None = None,
        strings: list[str] | None = None,
    ) -> None:
        self._leb128_values = deque(leb128_values or [])
        self._strings = deque(strings or [])
        self.last_message = b""
        self.closed = False

    def read_leb128(self) -> int:
        if not self._leb128_values:
            raise StreamCompleteException
        return self._leb128_values.popleft()

    def read_leb128_str(self) -> str:
        if not self._strings:
            raise StreamCompleteException
        return self._strings.popleft()

    def read_uint64(self) -> int:
        raise AssertionError("unexpected uint64 read")

    def read_bytes(self, sz: int) -> bytes:
        raise AssertionError("unexpected bytes read")

    def read_str_col(
        self,
        num_rows: int,
        encoding: str,
        nullable: bool = False,
        null_obj: Any = None,
    ) -> list[str]:
        raise AssertionError("unexpected string column read")

    def read_bytes_col(self, sz: int, num_rows: int) -> list[bytes]:
        raise AssertionError("unexpected bytes column read")

    def read_fixed_str_col(self, sz: int, num_rows: int, encoding: str) -> list[str]:
        raise AssertionError("unexpected fixed string column read")

    def read_array(self, array_type: str, num_rows: int) -> list[Any]:
        raise AssertionError("unexpected array read")

    def read_byte(self) -> int:
        raise AssertionError("unexpected byte read")

    def close(self) -> None:
        self.closed = True


def test_clickhouse_connect_streaming_controls_http_response_buffering() -> None:
    client = _RecordingHttpClient()

    # Normal query requests a server-side response boundary.
    HttpClient._query_with_context(
        client,
        QueryContext(query="SELECT 1", streaming=False),
    )

    # Row streaming disables that boundary.
    HttpClient._query_with_context(
        client,
        QueryContext(query="SELECT 1", streaming=True),
    )

    assert client.server_wait_values == [True, False]


def test_clickhouse_connect_native_parser_empty_result_boundaries() -> None:
    # EOF before the first Native block becomes an empty result with no schema.
    eof_result = NativeTransform.parse_response(_ScriptedNativeSource())
    assert eof_result.result_rows == []
    assert eof_result.column_names == ()

    # A valid zero-row Native block is also row-empty, but it preserves schema.
    zero_row_result = NativeTransform.parse_response(
        _ScriptedNativeSource(
            leb128_values=[1, 0],
            strings=["digest", "String"],
        )
    )
    assert zero_row_result.result_rows == []
    assert zero_row_result.column_names == ("digest",)
    assert [column_type.name for column_type in zero_row_result.column_types] == [
        "String"
    ]
