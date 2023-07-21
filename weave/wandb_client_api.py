# This is deprecated in favor of the new wandb_api.py module.
# TODO: remove uses of this and delete.

from wandb.apis import public
from wandb.sdk.internal.internal_api import _thread_local_api_settings
import typing

from . import errors


def wandb_public_api() -> public.Api:
    return public.Api(timeout=30)


def assert_wandb_authenticated() -> None:
    authenticated = (
        wandb_public_api().api_key is not None
        or _thread_local_api_settings.cookies is not None
    )
    if not authenticated:
        raise errors.WeaveWandbAuthenticationException(
            f"Unable to log data to W&B. Please authenticate by setting WANDB_API_KEY or running `wandb init`."
        )


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


def reset_wandb_thread_local_api_settings() -> None:
    _thread_local_api_settings.api_key = None
    _thread_local_api_settings.cookies = None
    _thread_local_api_settings.headers = None
