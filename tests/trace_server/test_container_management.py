from unittest.mock import MagicMock, Mock, patch

import httpx

from tests.trace_server.conftest_lib.container_management import _check_server_health


def _mock_client_with_get_side_effect(side_effect):
    client = Mock()
    client.get.side_effect = side_effect
    client_factory = MagicMock()
    client_factory.return_value.__enter__.return_value = client
    client_factory.return_value.__exit__.return_value = False
    return client_factory


@patch("tests.trace_server.conftest_lib.container_management.time.sleep")
def test_check_server_health_retries_transient_httpx_errors_and_statuses(mock_sleep):
    # Transient protocol error during startup, then success.
    client_factory = _mock_client_with_get_side_effect(
        [
            httpx.RemoteProtocolError("server booting"),
            Mock(status_code=200),
        ]
    )
    with patch(
        "tests.trace_server.conftest_lib.container_management.httpx.Client",
        client_factory,
    ):
        assert _check_server_health("http://localhost:8123/", "ping", num_retries=2)
    assert mock_sleep.call_count == 1

    mock_sleep.reset_mock()

    # Non-200 status should also retry and recover cleanly.
    client_factory = _mock_client_with_get_side_effect(
        [
            Mock(status_code=503),
            Mock(status_code=200),
        ]
    )
    with patch(
        "tests.trace_server.conftest_lib.container_management.httpx.Client",
        client_factory,
    ):
        assert _check_server_health("http://localhost:8123/", "ping", num_retries=2)
    assert mock_sleep.call_count == 1


@patch("tests.trace_server.conftest_lib.container_management.time.sleep")
def test_check_server_health_reports_last_httpx_error(mock_sleep, capsys):
    client_factory = _mock_client_with_get_side_effect(
        [
            httpx.RemoteProtocolError("server disconnected without sending a response"),
            httpx.ConnectError("connection refused"),
        ]
    )
    with patch(
        "tests.trace_server.conftest_lib.container_management.httpx.Client",
        client_factory,
    ):
        assert (
            _check_server_health("http://localhost:8123/", "ping", num_retries=2)
            is False
        )

    captured = capsys.readouterr()
    assert "Server not healthy @ http://localhost:8123/ping" in captured.out
    assert "ConnectError" in captured.out
    assert mock_sleep.call_count == 2
