from __future__ import annotations

import base64
import json
import os
from datetime import datetime, timedelta, timezone
from functools import partial
from io import BytesIO
from pathlib import Path

import httpx
import pytest
import requests
from requests.adapters import HTTPAdapter
from urllib3.response import HTTPResponse

from weave.compat.wandb.wandb_thin.errors import AuthenticationError
from weave.trace_server_bindings import remote_http_trace_server
from weave.vendor.weave_server_sdk import DefaultHttpxClient
from weave.wandb_interface import auth

API_URL = "https://api.wandb.test"
TRACE_URL = "https://trace.wandb.test"


def test_api_key_credentials_support_basic_and_bearer_auth() -> None:
    credentials = auth.ApiKeyCredentials("secret")

    assert credentials.authorization_header() == (
        "Basic " + base64.b64encode(b"api:secret").decode()
    )
    assert credentials.bearer_token() == "secret"
    assert credentials.wal_seed() == "secret"


def test_identity_credentials_exchange_once_and_reuse_cache(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    token_file = tmp_path / "identity.jwt"
    token_file.write_text("identity-token", encoding="utf-8")
    credentials_file = tmp_path / "credentials.json"
    requests: list[httpx.Request] = []

    def exchange(
        url: str,
        *,
        data: dict[str, str],
        headers: dict[str, str],
        verify: bool,
    ) -> httpx.Response:
        request = httpx.Request("POST", url)
        requests.append(request)
        assert data == {
            "grant_type": auth.TOKEN_GRANT_TYPE,
            "assertion": "identity-token",
        }
        assert headers == {"Content-Type": "application/x-www-form-urlencoded"}
        assert verify is True
        return httpx.Response(
            200,
            json={"access_token": "access-token", "expires_in": 3600},
            request=request,
        )

    monkeypatch.setattr(auth.httpx, "post", exchange)
    credentials = auth.IdentityTokenCredentials(
        "https://api.wandb.test",
        token_file,
        credentials_file,
    )

    assert credentials.authorization_header() == "Bearer access-token"
    assert credentials.authorization_header() == "Bearer access-token"
    assert credentials.wal_seed() == (f"https://api.wandb.test\0{token_file.resolve()}")
    assert len(requests) == 1
    if os.name != "nt":
        assert credentials_file.stat().st_mode & 0o777 == 0o600


def test_identity_credentials_fall_back_to_memory_when_cache_is_read_only(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    token_file = tmp_path / "identity.jwt"
    token_file.write_text("identity-token", encoding="utf-8")
    request = httpx.Request("POST", "https://api.wandb.test/oidc/token")
    exchange_count = 0

    def post(*args, **kwargs) -> httpx.Response:
        nonlocal exchange_count
        exchange_count += 1
        return httpx.Response(
            200,
            json={"access_token": "access-token", "expires_in": 3600},
            request=request,
        )

    def fail_write(*args) -> None:
        raise OSError("read-only filesystem")

    credentials = auth.IdentityTokenCredentials(
        "https://api.wandb.test",
        token_file,
        tmp_path / "credentials.json",
    )
    monkeypatch.setattr(auth.httpx, "post", post)
    monkeypatch.setattr(credentials, "_write_cached_token", fail_write)
    caplog.set_level("WARNING", logger=auth.__name__)

    assert credentials.access_token() == "access-token"
    assert credentials.access_token() == "access-token"
    assert exchange_count == 1
    assert [record.message for record in caplog.records] == [
        f"Unable to persist W&B access token to {credentials.credentials_file}; "
        "using in-process caching"
    ]


def test_identity_credentials_refresh_expiring_token(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    token_file = tmp_path / "identity.jwt"
    token_file.write_text("identity-token", encoding="utf-8")
    credentials_file = tmp_path / "credentials.json"
    credentials_file.write_text(
        json.dumps(
            {
                "credentials": {
                    "https://api.wandb.test": {
                        "access_token": "expiring-token",
                        "expires_at": (
                            datetime.now(timezone.utc) + timedelta(minutes=1)
                        ).strftime(auth.EXPIRES_AT_FORMAT),
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    request = httpx.Request("POST", "https://api.wandb.test/oidc/token")

    def post(*args, **kwargs) -> httpx.Response:
        return httpx.Response(
            200,
            json={"access_token": "refreshed-token", "expires_in": 3600},
            request=request,
        )

    monkeypatch.setattr(auth.httpx, "post", post)
    credentials = auth.IdentityTokenCredentials(
        "https://api.wandb.test",
        token_file,
        credentials_file,
    )

    assert credentials.bearer_token() == "refreshed-token"


def test_identity_credentials_reject_invalid_exchange_response(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    token_file = tmp_path / "identity.jwt"
    token_file.write_text("identity-token", encoding="utf-8")
    request = httpx.Request("POST", "https://api.wandb.test/oidc/token")
    monkeypatch.setattr(
        auth.httpx,
        "post",
        lambda *args, **kwargs: httpx.Response(
            200,
            json={"expires_in": 3600},
            request=request,
        ),
    )
    credentials = auth.IdentityTokenCredentials(
        "https://api.wandb.test",
        token_file,
        tmp_path / "credentials.json",
    )

    with pytest.raises(AuthenticationError, match="invalid response"):
        credentials.access_token()


def test_identity_credentials_reject_missing_identity_file(tmp_path: Path) -> None:
    token_file = tmp_path / "missing.jwt"
    credentials = auth.IdentityTokenCredentials(
        "https://api.wandb.test",
        token_file,
        tmp_path / "credentials.json",
    )

    with pytest.raises(AuthenticationError) as exc_info:
        credentials.access_token()

    assert str(exc_info.value) == f"Identity token file not found: {token_file}"


def test_identity_credentials_reject_empty_identity_file(tmp_path: Path) -> None:
    token_file = tmp_path / "identity.jwt"
    token_file.write_text("", encoding="utf-8")
    credentials = auth.IdentityTokenCredentials(
        "https://api.wandb.test",
        token_file,
        tmp_path / "credentials.json",
    )

    with pytest.raises(AuthenticationError) as exc_info:
        credentials.access_token()

    assert str(exc_info.value) == f"Identity token file is empty: {token_file}"


def test_identity_credentials_reject_failed_exchange(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    token_file = tmp_path / "identity.jwt"
    token_file.write_text("identity-token", encoding="utf-8")
    request = httpx.Request("POST", "https://api.wandb.test/oidc/token")
    monkeypatch.setattr(
        auth.httpx,
        "post",
        lambda *args, **kwargs: httpx.Response(
            401,
            text="invalid assertion",
            request=request,
        ),
    )
    credentials = auth.IdentityTokenCredentials(
        "https://api.wandb.test",
        token_file,
        tmp_path / "credentials.json",
    )

    with pytest.raises(AuthenticationError) as exc_info:
        credentials.access_token()

    assert str(exc_info.value) == (
        "Failed to exchange identity token: 401, invalid assertion"
    )


def test_identity_credentials_cache_exchange_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    token_file = tmp_path / "identity.jwt"
    token_file.write_text("identity-token", encoding="utf-8")
    request = httpx.Request("POST", "https://api.wandb.test/oidc/token")
    exchange_count = 0
    now = 100.0

    def post(*args, **kwargs) -> httpx.Response:
        nonlocal exchange_count
        exchange_count += 1
        if exchange_count == 1:
            return httpx.Response(
                503,
                text="unavailable",
                request=request,
            )
        return httpx.Response(
            200,
            json={"access_token": "access-token", "expires_in": 3600},
            request=request,
        )

    monkeypatch.setattr(auth.httpx, "post", post)
    monkeypatch.setattr(auth.time, "monotonic", lambda: now)
    credentials = auth.IdentityTokenCredentials(
        "https://api.wandb.test",
        token_file,
        tmp_path / "credentials.json",
    )

    for _ in range(2):
        with pytest.raises(AuthenticationError) as exc_info:
            credentials.access_token()
        assert str(exc_info.value) == (
            "Failed to exchange identity token: 503, unavailable"
        )
    assert exchange_count == 1

    now += auth.TOKEN_EXCHANGE_FAILURE_COOLDOWN_SECONDS

    assert credentials.access_token() == "access-token"
    assert exchange_count == 2


def test_identity_credentials_wrap_transport_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    token_file = tmp_path / "identity.jwt"
    token_file.write_text("identity-token", encoding="utf-8")

    def raise_connect_error(*args, **kwargs):
        raise httpx.ConnectError("network unavailable")

    monkeypatch.setattr(auth.httpx, "post", raise_connect_error)
    credentials = auth.IdentityTokenCredentials(
        "https://api.wandb.test",
        token_file,
        tmp_path / "credentials.json",
    )

    with pytest.raises(AuthenticationError) as exc_info:
        credentials.access_token()

    assert str(exc_info.value) == (
        "Failed to exchange identity token: network unavailable"
    )


def test_identity_credentials_reject_empty_access_token(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    token_file = tmp_path / "identity.jwt"
    token_file.write_text("identity-token", encoding="utf-8")
    request = httpx.Request("POST", "https://api.wandb.test/oidc/token")
    monkeypatch.setattr(
        auth.httpx,
        "post",
        lambda *args, **kwargs: httpx.Response(
            200,
            json={"access_token": "", "expires_in": 3600},
            request=request,
        ),
    )
    credentials = auth.IdentityTokenCredentials(
        "https://api.wandb.test",
        token_file,
        tmp_path / "credentials.json",
    )

    with pytest.raises(AuthenticationError) as exc_info:
        credentials.access_token()

    assert str(exc_info.value) == (
        "Identity token exchange returned an invalid access token"
    )


@pytest.mark.parametrize(
    "cache",
    [
        [],
        {},
        {"credentials": {}},
        {
            "credentials": {
                "https://api.wandb.test": {
                    "access_token": 123,
                    "expires_at": "invalid",
                }
            }
        },
        {
            "credentials": {
                "https://api.wandb.test": {
                    "access_token": "token",
                    "expires_at": "invalid",
                }
            }
        },
    ],
)
def test_identity_credentials_ignore_invalid_cache(
    tmp_path: Path, cache: object
) -> None:
    credentials_file = tmp_path / "credentials.json"
    credentials_file.write_text(json.dumps(cache), encoding="utf-8")
    credentials = auth.IdentityTokenCredentials(
        "https://api.wandb.test",
        tmp_path / "identity.jwt",
        credentials_file,
    )

    assert credentials._read_cached_token() is None


def test_resolve_identity_credentials_ignores_netrc_api_key(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    token_file = tmp_path / "identity.jwt"
    monkeypatch.delenv("WANDB_API_KEY", raising=False)
    monkeypatch.setenv("WANDB_IDENTITY_TOKEN_FILE", str(token_file))
    monkeypatch.setenv("WANDB_CREDENTIALS_FILE", str(tmp_path / "credentials.json"))
    monkeypatch.setattr(auth.env, "weave_wandb_api_key", lambda: "netrc-key")

    credentials = auth.get_wandb_credentials()

    assert isinstance(credentials, auth.IdentityTokenCredentials)
    assert credentials.token_file == token_file


def test_resolve_credentials_rejects_conflicting_environment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("WANDB_API_KEY", "api-key")
    monkeypatch.setenv("WANDB_IDENTITY_TOKEN_FILE", str(tmp_path / "identity.jwt"))

    with pytest.raises(AuthenticationError, match="Both WANDB_API_KEY"):
        auth.get_wandb_credentials()


def test_resolve_api_key_and_missing_credentials(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("WANDB_API_KEY", raising=False)
    monkeypatch.delenv("WANDB_IDENTITY_TOKEN_FILE", raising=False)
    monkeypatch.setattr(auth.env, "weave_wandb_api_key", lambda: "api-key")

    credentials = auth.get_wandb_credentials()

    assert isinstance(credentials, auth.ApiKeyCredentials)
    assert credentials.api_key == "api-key"

    monkeypatch.setattr(auth.env, "weave_wandb_api_key", lambda: None)
    assert auth.get_wandb_credentials() is None


def test_httpx_auth_refreshes_authorization_for_each_request() -> None:
    credentials = _RotatingCredentials()
    received: list[str] = []

    def handle(request: httpx.Request) -> httpx.Response:
        received.append(request.headers["Authorization"])
        return httpx.Response(200)

    with httpx.Client(
        transport=httpx.MockTransport(handle),
        auth=credentials.httpx_auth(),
    ) as client:
        client.get("https://trace.wandb.test/server_info")
        client.get("https://trace.wandb.test/server_info")

    assert received == ["Bearer token-1", "Bearer token-2"]


def test_requests_auth_refreshes_authorization_for_each_request() -> None:
    credentials = _RotatingCredentials()
    requests_auth = credentials.requests_auth()
    first = requests.Request("GET", "https://trace.wandb.test/server_info").prepare()
    second = requests.Request("GET", "https://trace.wandb.test/server_info").prepare()

    requests_auth(first)
    requests_auth(second)

    assert first.headers["Authorization"] == "Bearer token-1"
    assert second.headers["Authorization"] == "Bearer token-2"


@pytest.fixture
def identity_credentials(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> tuple[auth.IdentityTokenCredentials, list[str]]:
    token_file = tmp_path / "identity.jwt"
    token_file.write_text("identity-token", encoding="utf-8")
    credentials = auth.IdentityTokenCredentials(
        API_URL, token_file, tmp_path / "credentials.json"
    )
    exchanges: list[str] = []

    def exchange(url: str, **kwargs: object) -> httpx.Response:
        assert url == f"{API_URL}/oidc/token"
        token = f"token-{len(exchanges) + 1}"
        exchanges.append(token)
        return httpx.Response(200, json={"access_token": token, "expires_in": 3600})

    monkeypatch.setattr(auth.httpx, "post", exchange)

    return credentials, exchanges


@pytest.mark.parametrize(
    ("statuses", "expected_tokens"),
    [
        ((401, 200), ["token-1", "token-2"]),
        ((401, 401), ["token-1", "token-2"]),
        ((403,), ["token-1"]),
        ((400,), ["token-1"]),
        ((503,), ["token-1"]),
    ],
)
def test_httpx_identity_auth_retries_only_one_401(
    identity_credentials: tuple[auth.IdentityTokenCredentials, list[str]],
    statuses: tuple[int, ...],
    expected_tokens: list[str],
) -> None:
    credentials, exchanges = identity_credentials
    statuses_to_send = iter(statuses)
    received: list[tuple[str, bytes]] = []

    def handle(request: httpx.Request) -> httpx.Response:
        received.append((request.headers["Authorization"], request.content))
        return httpx.Response(next(statuses_to_send))

    assert credentials.access_token() == "token-1"
    with httpx.Client(
        transport=httpx.MockTransport(handle), auth=credentials.httpx_auth()
    ) as client:
        response = client.post(TRACE_URL, content=iter([b"payload"]))

    assert response.status_code == statuses[-1]
    assert received == [(f"Bearer {token}", b"payload") for token in expected_tokens]
    assert exchanges == expected_tokens
    assert _cached_access_token(credentials) == expected_tokens[-1]


def test_httpx_api_key_does_not_retry_401() -> None:
    credentials = auth.ApiKeyCredentials("secret")
    received: list[str] = []

    def handle(request: httpx.Request) -> httpx.Response:
        received.append(request.headers["Authorization"])
        return httpx.Response(401)

    with httpx.Client(
        transport=httpx.MockTransport(handle), auth=credentials.httpx_auth()
    ) as client:
        response = client.get(TRACE_URL)

    assert response.status_code == 401
    assert received == ["Basic YXBpOnNlY3JldA=="]


def test_invalidate_preserves_tokens_refreshed_by_another_credentials_instance(
    identity_credentials: tuple[auth.IdentityTokenCredentials, list[str]],
) -> None:
    credentials, exchanges = identity_credentials
    other = auth.IdentityTokenCredentials(
        credentials.base_url, credentials.token_file, credentials.credentials_file
    )
    assert credentials.access_token() == other.access_token() == "token-1"

    other.invalidate("token-1")
    assert other.access_token() == "token-2"

    credentials.invalidate("token-1")
    assert _cached_access_token(credentials) == "token-2"
    assert credentials.access_token() == "token-2"

    other.invalidate("token-1")
    credentials.credentials_file.unlink()
    assert other.access_token() == "token-2"
    assert exchanges == ["token-1", "token-2"]


def test_invalidate_rejects_on_disk_token_when_persistence_fails(
    identity_credentials: tuple[auth.IdentityTokenCredentials, list[str]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    credentials, exchanges = identity_credentials
    assert credentials.access_token() == "token-1"

    def fail_replace(data: dict[str, object]) -> None:
        raise OSError("read-only filesystem")

    monkeypatch.setattr(credentials, "_replace_credentials_file", fail_replace)
    credentials.invalidate("token-1")
    assert credentials.access_token() == "token-2"
    credentials.invalidate("token-2")
    assert credentials.access_token() == "token-3"
    assert _cached_access_token(credentials) == "token-1"
    assert exchanges == ["token-1", "token-2", "token-3"]


@pytest.mark.parametrize("retry_status", [200, 401])
def test_requests_identity_auth_replays_body_once_on_401(
    identity_credentials: tuple[auth.IdentityTokenCredentials, list[str]],
    monkeypatch: pytest.MonkeyPatch,
    retry_status: int,
) -> None:
    credentials, exchanges = identity_credentials
    received: list[tuple[str, bytes]] = []
    statuses_to_send = iter([401, retry_status])

    def send(
        adapter: HTTPAdapter, request: requests.PreparedRequest, **kwargs: object
    ) -> requests.Response:
        assert isinstance(request.body, BytesIO)
        received.append((request.headers["Authorization"], request.body.read()))
        raw = HTTPResponse(body=BytesIO(b"{}"), status=next(statuses_to_send))
        return adapter.build_response(request, raw)

    monkeypatch.setattr(HTTPAdapter, "send", send)
    with requests.Session() as session:
        session.auth = credentials.requests_auth()
        response = session.post(TRACE_URL, data=BytesIO(b"payload"))

    assert response.status_code == retry_status
    assert [prior.status_code for prior in response.history] == [401]
    assert received == [("Bearer token-1", b"payload"), ("Bearer token-2", b"payload")]
    assert exchanges == ["token-1", "token-2"]
    assert _cached_access_token(credentials) == "token-2"


def test_trace_server_retries_with_refreshed_identity_token(
    identity_credentials: tuple[auth.IdentityTokenCredentials, list[str]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    credentials, exchanges = identity_credentials
    received: list[tuple[str, str]] = []
    statuses_to_send = iter([401, 200, 200])
    server_info = {
        "min_required_weave_python_version": "0.52.0",
        "trace_server_version": "1.0.0",
    }

    def handle(request: httpx.Request) -> httpx.Response:
        received.append((request.url.path, request.headers["Authorization"]))
        return httpx.Response(next(statuses_to_send), json=server_info)

    monkeypatch.setattr(
        remote_http_trace_server,
        "DefaultHttpxClient",
        partial(DefaultHttpxClient, transport=httpx.MockTransport(handle)),
    )
    server = remote_http_trace_server.RemoteHTTPTraceServer(TRACE_URL)
    server.set_auth(credentials)

    assert server.server_info().model_dump() == server_info
    assert server.server_info().model_dump() == server_info
    assert received == [
        ("/server_info", "Bearer token-1"),
        ("/server_info", "Bearer token-2"),
        ("/server_info", "Bearer token-2"),
    ]
    assert exchanges == ["token-1", "token-2"]
    assert _cached_access_token(credentials) == "token-2"


def _cached_access_token(credentials: auth.IdentityTokenCredentials) -> str:
    data = json.loads(credentials.credentials_file.read_text(encoding="utf-8"))
    token = data["credentials"][credentials.base_url]["access_token"]
    assert isinstance(token, str)

    return token


class _RotatingCredentials(auth.ApiKeyCredentials):
    def __init__(self) -> None:
        super().__init__("unused")
        self.request_count = 0

    def authorization_header(self) -> str:
        self.request_count += 1

        return f"Bearer token-{self.request_count}"
