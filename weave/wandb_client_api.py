# This is deprecated in favor of the new wandb_api.py module.
# TODO: remove uses of this and delete.

from wandb.apis import public
from wandb.sdk.internal.internal_api import _thread_local_api_settings
import logging
import typing

from . import errors

import graphql
from graphql import GraphQLSchema

from requests import exceptions


def wandb_public_api() -> public.Api:
    return public.Api(timeout=30)


def assert_wandb_authenticated() -> None:
    authenticated = (
        wandb_public_api().api_key is not None
        or _thread_local_api_settings.cookies is not None
    )
    if not authenticated:
        raise errors.WeaveWandbAuthenticationException(
            "Unable to log data to W&B. Please authenticate by setting WANDB_API_KEY or running `wandb init`."
        )


def query_with_retry(
    query_str: str,
    variables: dict[str, typing.Any] = {},
    num_timeout_retries: int = 0,
) -> typing.Any:
    if num_timeout_retries < 0:
        raise ValueError("num_timeout_retries must be >= 0")
    for attempt_no in range(num_timeout_retries + 1):
        try:
            return wandb_public_api().client.execute(
                public.gql(query_str),
                variable_values=variables,
            )
        except exceptions.Timeout as e:
            if attempt_no == num_timeout_retries:
                raise
            logging.warn(
                f'wandb GQL query timed out: "{e}", retrying (num_attempts={attempt_no + 1})'
            )


def introspect_server_schema(num_timeout_retries: int = 0) -> GraphQLSchema:
    introspection_query = graphql.get_introspection_query()
    payload = query_with_retry(introspection_query, {}, num_timeout_retries)
    return graphql.build_client_schema(payload)


def wandb_gql_query(
    query_str: str,
    variables: dict[str, typing.Any] = {},
    num_timeout_retries: int = 0,
) -> typing.Any:
    return query_with_retry(query_str, variables, num_timeout_retries)


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


_WANDB_CLIENT_PATCHED = False


def do_patch() -> None:
    global _WANDB_CLIENT_PATCHED
    if _WANDB_CLIENT_PATCHED:
        return

    ### Start _parse_artifact_path Patch ###
    # Can be removed after https://github.com/wandb/wandb/pull/6083 is merged and deployed.
    orig_parse_artifact_path = public.Api._parse_artifact_path

    def new_parse_artifact_path(self, path):  # type: ignore
        # Adding this short circuit skips the potential access of
        # self.default_entity which incurs a network call. However, if the path
        # is fully qualified, then this `entity` is thrown away.
        parts = [] if path is None else path.split("/")
        if len(parts) == 3:
            return parts
        return orig_parse_artifact_path(self, path)

    public.Api._parse_artifact_path = new_parse_artifact_path  # type: ignore
    ### End _parse_artifact_path Patch ###

    _WANDB_CLIENT_PATCHED = True


do_patch()
