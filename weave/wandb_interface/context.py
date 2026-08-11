from __future__ import annotations

from weave.wandb_interface.auth import (
    ApiKeyCredentials,
    IdentityTokenCredentials,
    WandbCredentials,
    get_wandb_credentials,
)


def get_wandb_auth_context() -> WandbCredentials | None:
    return get_wandb_credentials()


def get_wandb_api_context() -> str | None:
    credentials = get_wandb_auth_context()
    if isinstance(credentials, ApiKeyCredentials):
        return credentials.api_key
    if isinstance(credentials, IdentityTokenCredentials):
        return credentials.access_token()
    return None
