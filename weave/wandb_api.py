# Official interface for interacting with the W&B API. All
# Weave interactions with the Weave API should go through this
# module.

import dataclasses
import typing
import graphql
import gql
import aiohttp
import contextlib
import contextvars
import os

from gql.transport.aiohttp import AIOHTTPTransport
from gql.transport.requests import RequestsHTTPTransport


from . import engine_trace
from . import environment as weave_env
from . import wandb_client_api


tracer = engine_trace.tracer()  # type: ignore


@dataclasses.dataclass
class WandbApiContext:
    user_id: str
    api_key: typing.Optional[str] = None
    headers: typing.Optional[dict[str, str]] = None
    cookies: typing.Optional[dict[str, str]] = None

    @classmethod
    def from_json(cls, json: typing.Any) -> "WandbApiContext":
        return cls(**json)

    def to_json(self) -> typing.Any:
        return dataclasses.asdict(self)


_wandb_api_context: contextvars.ContextVar[
    typing.Optional[WandbApiContext]
] = contextvars.ContextVar("_weave_api_context", default=None)


def set_wandb_api_context(
    user_id: str,
    api_key: typing.Optional[str],
    headers: typing.Optional[dict],
    cookies: typing.Optional[dict],
) -> typing.Optional[contextvars.Token[typing.Optional[WandbApiContext]]]:
    cur_ctx = get_wandb_api_context()
    if cur_ctx:
        # WANDB API context is only allowed to be set once per thread, since we
        # need to use thread local storage to communicate the context to the wandb
        # lib right now.
        return None
    wandb_client_api.set_wandb_thread_local_api_settings(api_key, cookies, headers)
    return _wandb_api_context.set(WandbApiContext(user_id, api_key, headers, cookies))


def reset_wandb_api_context(
    token: typing.Optional[contextvars.Token[typing.Optional[WandbApiContext]]],
) -> None:
    if token is None:
        return
    wandb_client_api.reset_wandb_thread_local_api_settings()
    _wandb_api_context.reset(token)


@contextlib.contextmanager
def wandb_api_context(
    ctx: typing.Optional[WandbApiContext],
) -> typing.Generator[None, None, None]:
    if ctx:
        token = set_wandb_api_context(
            ctx.user_id, ctx.api_key, ctx.headers, ctx.cookies
        )
    try:
        yield
    finally:
        if ctx:
            reset_wandb_api_context(token)


def get_wandb_api_context() -> typing.Optional[WandbApiContext]:
    return _wandb_api_context.get()


@contextlib.contextmanager
def from_environment() -> typing.Generator[None, None, None]:
    cookie = weave_env.weave_wandb_cookie()
    token = None
    if cookie:
        cookies = {"wandb": cookie}
        headers = {"use-admin-privileges": "true", "x-origin": "https://app.wandb.test"}
        token = set_wandb_api_context("admin", "<not_used>", headers, cookies)
    try:
        yield
    finally:
        if token:
            reset_wandb_api_context(token)


class WandbApiSync:
    @property
    def user_agent(self) -> str:
        return "Weave Client"

    def __init__(self) -> None:
        url_base = weave_env.wandb_base_url()
        self.client = gql.Client(
            transport=RequestsHTTPTransport(
                use_json=True,
                # this timeout won't apply when the DNS lookup fails. in that case, it will be 60s
                # https://bugs.python.org/issue22889
                timeout=30,
                url="%s/graphql" % url_base,
            )
        )
        self.session = self.client.connect_sync()

    def query(self, query: graphql.DocumentNode, **kwargs: typing.Any) -> typing.Any:
        wandb_context = get_wandb_api_context()
        headers = {
            "User-Agent": self.user_agent,
            "Use-Admin-Privileges": "true",
        }
        cookies = {}
        if wandb_context is not None:
            headers.update(wandb_context.headers or {})
            headers = wandb_context.headers
            cookies = wandb_context.cookies

        return self.session.execute(
            query, kwargs, extra_args={"headers": headers, "cookies": cookies}
        )


class WandbApiAsync:
    def __init__(self) -> None:
        self.connector = aiohttp.TCPConnector(limit=50)

    async def query(
        self, query: graphql.DocumentNode, **kwargs: typing.Any
    ) -> typing.Any:
        wandb_context = get_wandb_api_context()
        headers = None
        cookies = None
        if wandb_context is not None:
            headers = wandb_context.headers
            cookies = wandb_context.cookies
        url_base = weave_env.wandb_base_url()
        transport = AIOHTTPTransport(
            url=url_base + "/graphql",
            client_session_args={
                "connector": self.connector,
                "connector_owner": False,
            },
            headers=headers,
            cookies=cookies,
        )
        # Warning: we do not use the recommended context manager pattern, because we're
        # using connector_owner to tell the session not to close our connection pool.
        # There is a bug in aiohttp that causes session close to hang for the ssl_close_timeout
        # which is 10 seconds by default. See issue: https://github.com/graphql-python/gql/issues/381
        # Closing the session just closes the connector, which we don't want anyway, so we don't
        # bother.
        client = gql.Client(transport=transport, fetch_schema_from_transport=False)
        session = await client.connect_async(reconnecting=False)  # type: ignore
        return await session.execute(query, kwargs)

    SERVER_INFO_QUERY = gql.gql(
        """
        query ServerInfo {
            serverInfo {
            frontendHost
            }
        }
        """
    )

    async def server_info(self) -> typing.Any:
        return await self.query(self.SERVER_INFO_QUERY)

    ARTIFACT_MANIFEST_QUERY = gql.gql(
        """
        query ArtifactManifest(
            $entityName: String!,
            $projectName: String!,
            $name: String!
        ) {
            project(name: $projectName, entityName: $entityName) {
                artifact(name: $name) {
                    currentManifest {
                        id
                        file {
                            id
                            directUrl
                        }
                    }
                }
            }
        }
        """
    )

    async def artifact_manifest_url(
        self, entity_name: str, project_name: str, name: str
    ) -> typing.Optional[str]:
        try:
            result = await self.query(
                self.ARTIFACT_MANIFEST_QUERY,
                entityName=entity_name,
                projectName=project_name,
                name=name,
            )
        except gql.transport.exceptions.TransportQueryError as e:
            return None
        project = result["project"]
        if project is None:
            return None
        artifact = project["artifact"]
        if artifact is None:
            return None
        current_manifest = artifact["currentManifest"]
        if current_manifest is None:
            return None
        file = current_manifest["file"]
        if file is None:
            return None
        return file["directUrl"]


sync_api = None


def get_sync_wandb_api() -> WandbApiSync:
    global sync_api
    if sync_api is None:
        sync_api = WandbApiSync()
    return sync_api


async def get_async_wandb_api() -> WandbApiAsync:
    return WandbApiAsync()
