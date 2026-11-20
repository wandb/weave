from __future__ import annotations

import base64
import functools
import json
import logging
import os
import threading
import time
from abc import ABC, abstractmethod
from collections.abc import Generator, Mapping
from datetime import datetime, timedelta, timezone
from http import HTTPStatus
from pathlib import Path
from typing import TypedDict

import httpx
from requests import PreparedRequest, Response
from requests.cookies import RequestsCookieJar
from requests.utils import rewind_body
from typing_extensions import Unpack

from weave.compat.wandb.wandb_thin.errors import AuthenticationError
from weave.trace import env

logger = logging.getLogger(__name__)

CREDENTIALS_FILE_ENV = "WANDB_CREDENTIALS_FILE"
DEFAULT_CREDENTIALS_FILE = Path("~/.config/wandb/credentials.json").expanduser()
EXPIRES_AT_FORMAT = "%Y-%m-%d %H:%M:%S"
IDENTITY_TOKEN_FILE_ENV = "WANDB_IDENTITY_TOKEN_FILE"
TOKEN_EXCHANGE_FAILURE_COOLDOWN_SECONDS = 30
TOKEN_GRANT_TYPE = "urn:ietf:params:oauth:grant-type:jwt-bearer"
TOKEN_REFRESH_SKEW = timedelta(minutes=5)
WANDB_API_BASIC_USERNAME = "api"


class WandbCredentials(ABC):
    @abstractmethod
    def authorization_header(self) -> str: ...

    @abstractmethod
    def bearer_token(self) -> str: ...

    @abstractmethod
    def wal_seed(self) -> str: ...

    @abstractmethod
    def invalidate(self, token: str) -> None: ...

    def httpx_auth(self) -> httpx.Auth:
        return _WandbHttpxAuth(self)

    def requests_auth(self) -> _WandbRequestsAuth:
        return _WandbRequestsAuth(self)


class ApiKeyCredentials(WandbCredentials):
    def __init__(self, api_key: str) -> None:
        self.api_key = api_key

    def authorization_header(self) -> str:
        encoded = base64.b64encode(
            f"{WANDB_API_BASIC_USERNAME}:{self.api_key}".encode()
        ).decode()
        return f"Basic {encoded}"

    def bearer_token(self) -> str:
        return self.api_key

    def wal_seed(self) -> str:
        return self.api_key

    def invalidate(self, token: str) -> None:
        """Keep the configured API key."""


class IdentityTokenCredentials(WandbCredentials):
    def __init__(
        self,
        base_url: str,
        token_file: Path,
        credentials_file: Path,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.token_file = token_file
        self.credentials_file = credentials_file
        self._lock = threading.Lock()
        self._cached_access_token: tuple[str, datetime] | None = None
        self._rejected_file_token: str | None = None
        self._credentials_write_warning_emitted = False
        self._exchange_failure: tuple[float, str] | None = None

    def authorization_header(self) -> str:
        return f"Bearer {self.access_token()}"

    def bearer_token(self) -> str:
        return self.access_token()

    def wal_seed(self) -> str:
        return f"{self.base_url}\0{self.token_file.expanduser().resolve()}"

    def invalidate(self, token: str) -> None:
        with self._lock:
            if self._cached_access_token and self._cached_access_token[0] == token:
                self._cached_access_token = None
            try:
                self._drop_cached_token_from_file(token)
            except OSError:
                # Keep a rejected on-disk token out of the in-process cache.
                entry = self._read_credentials_entry()
                if entry.get("access_token") == token:
                    self._rejected_file_token = token
                self._warn_credentials_write_failed()

    def access_token(self) -> str:
        with self._lock:
            cached = self._read_cached_token()
            if cached is not None:
                return cached
            now = time.monotonic()
            if self._exchange_failure is not None:
                retry_at, message = self._exchange_failure
                if now < retry_at:
                    raise AuthenticationError(message)
            try:
                token, expires_at = self._exchange_token()
            except AuthenticationError as e:
                self._exchange_failure = (
                    now + TOKEN_EXCHANGE_FAILURE_COOLDOWN_SECONDS,
                    str(e),
                )
                raise
            self._exchange_failure = None
            self._cached_access_token = (token, expires_at)
            try:
                self._write_cached_token(token, expires_at)
            except OSError:
                self._warn_credentials_write_failed()
            return token

    def _read_cached_token(self) -> str | None:
        if self._cached_access_token is not None:
            cached_token, expires_at = self._cached_access_token
            if expires_at - TOKEN_REFRESH_SKEW > datetime.now(timezone.utc):
                return cached_token
            self._cached_access_token = None

        credentials = self._read_credentials_entry()
        token = credentials.get("access_token")
        if token == self._rejected_file_token:
            return None
        expires_at_value = credentials.get("expires_at")
        if not isinstance(token, str) or not isinstance(expires_at_value, str):
            return None
        try:
            expires_at = datetime.strptime(expires_at_value, EXPIRES_AT_FORMAT).replace(
                tzinfo=timezone.utc
            )
        except ValueError:
            return None
        if expires_at - TOKEN_REFRESH_SKEW <= datetime.now(timezone.utc):
            return None
        self._cached_access_token = (token, expires_at)
        return token

    def _exchange_token(self) -> tuple[str, datetime]:
        try:
            assertion = self.token_file.expanduser().read_text(encoding="utf-8").strip()
        except FileNotFoundError as e:
            raise AuthenticationError(
                f"Identity token file not found: {self.token_file}"
            ) from e
        except OSError as e:
            raise AuthenticationError(
                f"Failed to read identity token file: {self.token_file}"
            ) from e
        if not assertion:
            raise AuthenticationError(
                f"Identity token file is empty: {self.token_file}"
            )

        try:
            response = httpx.post(
                f"{self.base_url}/oidc/token",
                data={"grant_type": TOKEN_GRANT_TYPE, "assertion": assertion},
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                verify=env.ssl_verify(),
            )
        except httpx.HTTPError as e:
            raise AuthenticationError(f"Failed to exchange identity token: {e}") from e
        if response.status_code != 200:
            raise AuthenticationError(
                f"Failed to exchange identity token: "
                f"{response.status_code}, {response.text}"
            )

        try:
            payload = response.json()
            token = payload["access_token"]
            expires_in = float(payload["expires_in"])
        except (KeyError, TypeError, ValueError) as e:
            raise AuthenticationError(
                "Identity token exchange returned an invalid response"
            ) from e
        if not isinstance(token, str) or not token:
            raise AuthenticationError(
                "Identity token exchange returned an invalid access token"
            )
        return token, datetime.now(timezone.utc) + timedelta(seconds=expires_in)

    def _write_cached_token(self, token: str, expires_at: datetime) -> None:
        data = self._read_credentials_file()
        credentials = data.get("credentials")
        if not isinstance(credentials, dict):
            credentials = {}
            data["credentials"] = credentials
        credentials[self.base_url] = {
            "access_token": token,
            "expires_at": expires_at.astimezone(timezone.utc).strftime(
                EXPIRES_AT_FORMAT
            ),
        }
        self._replace_credentials_file(data)
        self._rejected_file_token = None

    def _drop_cached_token_from_file(self, token: str) -> None:
        data = self._read_credentials_file()
        entries = data.get("credentials")
        if not isinstance(entries, dict):
            return
        entry = entries.get(self.base_url)
        if not isinstance(entry, dict):
            return
        if entry.get("access_token") != token:
            return

        del entries[self.base_url]
        self._replace_credentials_file(data)

    def _read_credentials_entry(self) -> dict[str, object]:
        entries = self._read_credentials_file().get("credentials")
        if not isinstance(entries, dict):
            return {}
        entry = entries.get(self.base_url)
        if not isinstance(entry, dict):
            return {}

        return entry

    def _read_credentials_file(self) -> dict[str, object]:
        try:
            data = json.loads(self.credentials_file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}
        if not isinstance(data, dict):
            return {}

        return data

    def _warn_credentials_write_failed(self) -> None:
        if self._credentials_write_warning_emitted:
            return
        logger.warning(
            "Unable to persist W&B access token to %s; using in-process caching",
            self.credentials_file,
        )
        self._credentials_write_warning_emitted = True

    def _replace_credentials_file(self, data: dict[str, object]) -> None:
        self.credentials_file.parent.mkdir(parents=True, exist_ok=True)
        temporary_file = self.credentials_file.with_name(
            f".{self.credentials_file.name}.{os.getpid()}.{threading.get_ident()}.tmp"
        )
        try:
            temporary_file.write_text(
                json.dumps(data, indent=2) + "\n",
                encoding="utf-8",
            )
            os.chmod(temporary_file, 0o600)
            temporary_file.replace(self.credentials_file)
        finally:
            temporary_file.unlink(missing_ok=True)


class _WandbHttpxAuth(httpx.Auth):
    def __init__(self, credentials: WandbCredentials) -> None:
        self._credentials = credentials
        self.requires_request_body = isinstance(credentials, IdentityTokenCredentials)

    def auth_flow(
        self, request: httpx.Request
    ) -> Generator[httpx.Request, httpx.Response, None]:
        authorization = self._credentials.authorization_header()
        request.headers["Authorization"] = authorization
        response = yield request
        if response.status_code != HTTPStatus.UNAUTHORIZED:
            return
        if not isinstance(self._credentials, IdentityTokenCredentials):
            return
        if response.request.headers.get("Authorization") != authorization:
            return

        self._credentials.invalidate(authorization.removeprefix("Bearer "))
        request.headers["Authorization"] = self._credentials.authorization_header()
        yield request


class _RequestsSendOptions(TypedDict, total=False):
    stream: bool
    timeout: float | tuple[float, float] | tuple[float, None] | None
    verify: bool | str
    cert: bytes | str | tuple[bytes | str, bytes | str] | None
    proxies: Mapping[str, str] | None


class _WandbRequestsAuth:
    def __init__(self, credentials: WandbCredentials) -> None:
        self._credentials = credentials

    def __call__(self, request: PreparedRequest) -> PreparedRequest:
        authorization = self._credentials.authorization_header()
        request.headers["Authorization"] = authorization
        if isinstance(self._credentials, IdentityTokenCredentials):
            retry = functools.partial(
                self._retry_unauthorized, authorization=authorization
            )
            request.hooks["response"].append(retry)

        return request

    def _retry_unauthorized(
        self,
        response: Response,
        *,
        authorization: str,
        **kwargs: Unpack[_RequestsSendOptions],
    ) -> Response:
        if response.status_code != HTTPStatus.UNAUTHORIZED:
            return response
        if response.request.headers.get("Authorization") != authorization:
            return response

        self._credentials.invalidate(authorization.removeprefix("Bearer "))
        request = response.request.copy()
        if getattr(request, "_body_position", None) is not None:
            rewind_body(request)

        _ = response.content
        response.close()
        cookies = getattr(request, "_cookies", None)
        if isinstance(cookies, RequestsCookieJar):
            cookies.update(response.cookies)
            request.headers.pop("Cookie", None)
            request.prepare_cookies(cookies)
        request.headers["Authorization"] = self._credentials.authorization_header()
        # Adapter sends bypass response hooks, so the retry cannot recurse.
        retry = response.connection.send(request, **kwargs)
        retry.history.append(response)

        return retry


@functools.cache
def _identity_token_credentials(
    base_url: str,
    token_file: str,
    credentials_file: str,
) -> IdentityTokenCredentials:
    return IdentityTokenCredentials(
        base_url,
        Path(token_file),
        Path(credentials_file),
    )


def get_wandb_credentials() -> WandbCredentials | None:
    environment_api_key = os.getenv("WANDB_API_KEY")
    identity_token_file = os.getenv(IDENTITY_TOKEN_FILE_ENV)
    if environment_api_key and identity_token_file:
        raise AuthenticationError(
            f"Both WANDB_API_KEY and {IDENTITY_TOKEN_FILE_ENV} are set, "
            "which is not allowed."
        )
    if identity_token_file:
        credentials_file = os.getenv(
            CREDENTIALS_FILE_ENV, str(DEFAULT_CREDENTIALS_FILE)
        )
        return _identity_token_credentials(
            env.wandb_base_url(),
            identity_token_file,
            credentials_file,
        )
    api_key = env.weave_wandb_api_key()
    if api_key:
        return ApiKeyCredentials(api_key)
    return None
