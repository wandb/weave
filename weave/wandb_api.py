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
    return public.Api()


def wandb_gql_query(query_str, variables={}):
    return wandb_public_api().client.execute(
        public.gql(query_str),
        variable_values=variables,
    )


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
