# This is deprecated in favor of the new wandb_api.py module.
# TODO: remove uses of this and delete.

from wandb.apis import public
from wandb.sdk.internal.internal_api import _thread_local_api_settings
import os
import typing


def wandb_public_api() -> public.Api:
    if "WEAVE_WANDB_COOKIE" in os.environ:
        if os.path.exists(os.path.expanduser("~/.netrc")):
            raise Exception("Please delete ~/.netrc to avoid using your credentials")
        cookies = {"wandb": os.environ["WEAVE_WANDB_COOKIE"]}
        headers = {"use-admin-privileges": "true", "x-origin": "https://app.wandb.test"}
        set_wandb_thread_local_api_settings("<not_used>", cookies, headers)
    return public.Api(timeout=30)


def wandb_gql_query(
    query_str: str, variables: dict[str, typing.Any] = {}
) -> typing.Any:
    return wandb_public_api().client.execute(
        public.gql(query_str),
        variable_values=variables,
    )


def set_wandb_thread_local_api_settings(
    api_key: typing.Optional[str],
    cookies: typing.Optional[typing.Dict],
    headers: typing.Optional[typing.Dict],
) -> None:
    _thread_local_api_settings.api_key = api_key
    _thread_local_api_settings.cookies = cookies
    _thread_local_api_settings.headers = headers


class WandbThreadLocalApiSettings(typing.TypedDict):
    api_key: typing.Optional[str]
    cookies: typing.Optional[dict]
    headers: typing.Optional[dict]


def copy_thread_local_api_settings() -> WandbThreadLocalApiSettings:
    # Used for copying settings to sub-threads
    return {
        "api_key": _thread_local_api_settings.api_key,
        "cookies": _thread_local_api_settings.cookies,
        "headers": _thread_local_api_settings.headers,
    }


def reset_wandb_thread_local_api_settings() -> None:
    _thread_local_api_settings.api_key = None
    _thread_local_api_settings.cookies = None
    _thread_local_api_settings.headers = None
