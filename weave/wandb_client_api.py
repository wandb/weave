# This is deprecated in favor of the new wandb_api.py module.
# TODO: remove uses of this and delete.

import dataclasses
import logging
from requests import ReadTimeout
from wandb.apis import public
from wandb.sdk.internal.internal_api import _thread_local_api_settings
import typing


def wandb_public_api(timeout: int = 30) -> public.Api:
    return public.Api(timeout=timeout)


@dataclasses.dataclass
class RetryingWandbPublicApiProxy:
    retry_timeouts: list[int] = dataclasses.field(default_factory=lambda: [2, 30])

    def _with_timeout_protection(
        self, fn: typing.Callable[[public.Api], typing.Any], label: str = ""
    ) -> typing.Any:
        for t_ndx, timeout in enumerate(self.retry_timeouts):
            try:
                return fn(wandb_public_api(timeout))
            except ReadTimeout as e:
                if t_ndx == len(self.retry_timeouts) - 1:
                    raise e
                else:
                    logging.warning(
                        f"WandbPublicApiProxy::{label} failed attempt {t_ndx} with timeout {timeout}, retrying with timeout {self.retry_timeouts[t_ndx+1]}"
                    )

    def execute(self, *args: typing.Any, **kwargs: typing.Any) -> typing.Any:
        return self._with_timeout_protection(
            lambda api: api.client.execute(*args, **kwargs), "execute"
        )

    def artifact(
        self, name: typing.Any, type: typing.Optional[typing.Any] = None
    ) -> public.Artifact:
        return self._with_timeout_protection(
            lambda api: api.artifact(name, type), "artifact"
        )

    def run(self, path: str = "") -> public.Run:
        return self._with_timeout_protection(lambda api: api.run(path), "run")


def wandb_gql_query(
    query_str: str, variables: dict[str, typing.Any] = {}
) -> typing.Any:
    return RetryingWandbPublicApiProxy().execute(
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
