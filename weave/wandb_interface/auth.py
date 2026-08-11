from __future__ import annotations

import base64
import functools
import json
import os
import threading
from abc import ABC, abstractmethod
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import httpx

from weave.compat.wandb.wandb_thin.errors import AuthenticationError
from weave.trace import env

IDENTITY_TOKEN_FILE_ENV = "WANDB_IDENTITY_TOKEN_FILE"
CREDENTIALS_FILE_ENV = "WANDB_CREDENTIALS_FILE"
DEFAULT_CREDENTIALS_FILE = Path("~/.config/wandb/credentials.json").expanduser()
TOKEN_GRANT_TYPE = "urn:ietf:params:oauth:grant-type:jwt-bearer"
TOKEN_REFRESH_SKEW = timedelta(minutes=5)
EXPIRES_AT_FORMAT = "%Y-%m-%d %H:%M:%S"


class WandbCredentials(ABC):
    @abstractmethod
    def authorization_header(self) -> str: ...

    @abstractmethod
    def bearer_token(self) -> str: ...

    @abstractmethod
    def wal_seed(self) -> str: ...

    def httpx_auth(self) -> httpx.Auth:
        return _WandbHttpxAuth(self)

    def requests_auth(self) -> _WandbRequestsAuth:
        return _WandbRequestsAuth(self)


class ApiKeyCredentials(WandbCredentials):
    def __init__(self, api_key: str) -> None:
        self.api_key = api_key

    def authorization_header(self) -> str:
        encoded = base64.b64encode(f"api:{self.api_key}".encode()).decode()
        return f"Basic {encoded}"

    def bearer_token(self) -> str:
        return self.api_key

    def wal_seed(self) -> str:
        return self.api_key


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

    def authorization_header(self) -> str:
        return f"Bearer {self.access_token()}"

    def bearer_token(self) -> str:
        return self.access_token()

    def wal_seed(self) -> str:
        return f"{self.base_url}\0{self.token_file.expanduser().resolve()}"

    def access_token(self) -> str:
        with self._lock:
            cached = self._read_cached_token()
            if cached is not None:
                return cached
            token, expires_at = self._exchange_token()
            self._write_cached_token(token, expires_at)
            return token

    def _read_cached_token(self) -> str | None:
        try:
            data = json.loads(self.credentials_file.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            return None

        if not isinstance(data, dict):
            return None
        all_credentials = data.get("credentials")
        if not isinstance(all_credentials, dict):
            return None
        credentials = all_credentials.get(self.base_url)
        if not isinstance(credentials, dict):
            return None
        token = credentials.get("access_token")
        expires_at_value = credentials.get("expires_at")
        if not isinstance(token, str) or not isinstance(expires_at_value, str):
            return None
        try:
            expires_at = datetime.strptime(expires_at_value, EXPIRES_AT_FORMAT).replace(
                tzinfo=UTC
            )
        except ValueError:
            return None
        if expires_at - TOKEN_REFRESH_SKEW <= datetime.now(UTC):
            return None
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
        return token, datetime.now(UTC) + timedelta(seconds=expires_in)

    def _write_cached_token(self, token: str, expires_at: datetime) -> None:
        data: dict[str, Any] = {"credentials": {}}
        try:
            existing = json.loads(self.credentials_file.read_text(encoding="utf-8"))
            if isinstance(existing, dict):
                data = existing
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            pass

        credentials = data.setdefault("credentials", {})
        if not isinstance(credentials, dict):
            credentials = {}
            data["credentials"] = credentials
        credentials[self.base_url] = {
            "access_token": token,
            "expires_at": expires_at.astimezone(UTC).strftime(EXPIRES_AT_FORMAT),
        }

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

    def auth_flow(self, request: httpx.Request):
        request.headers["Authorization"] = self._credentials.authorization_header()
        yield request


class _WandbRequestsAuth:
    def __init__(self, credentials: WandbCredentials) -> None:
        self._credentials = credentials

    def __call__(self, request: Any) -> Any:
        request.headers["Authorization"] = self._credentials.authorization_header()
        return request


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
