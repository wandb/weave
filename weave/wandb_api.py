import contextvars
from wandb.apis import public
from wandb.sdk.internal.internal_api import _thread_local_api_settings
from .context_state import _wandb_public_api

import typing


def wandb_public_api() -> public.Api:
    return public.Api()


def set_wandb_thread_local_api_settings(
    api_key: typing.Optional[str],
    cookies: typing.Optional[typing.Dict],
    headers: typing.Optional[typing.Dict],
):
    _thread_local_api_settings.api_key = api_key
    _thread_local_api_settings.cookies = cookies
    _thread_local_api_settings.headers = headers


def reset_wandb_thread_local_api_settings():
    _thread_local_api_settings.api_key = None
    _thread_local_api_settings.cookies = None
    _thread_local_api_settings.headers = None
