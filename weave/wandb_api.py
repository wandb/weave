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

from gql.transport.aiohttp import AIOHTTPTransport


from . import engine_trace


tracer = engine_trace.tracer()  # type: ignore


@dataclasses.dataclass
class WandbApiContext:
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


@contextlib.contextmanager
def wandb_api_context(ctx: WandbApiContext) -> typing.Generator[None, None, None]:
    token = _wandb_api_context.set(ctx)
    try:
        yield
    finally:
        _wandb_api_context.reset(token)


def get_wandb_api_context() -> WandbApiContext:
    context = _wandb_api_context.get()
    if context is not None:
        return context
    return WandbApiContext(
        api_key="",
        headers={},
        cookies={},
    )


class WandbApiAsync:
    def __init__(self) -> None:
        self.connector = aiohttp.TCPConnector(limit=50)

    async def query(
        self, query: graphql.DocumentNode, **kwargs: typing.Any
    ) -> typing.Any:
        wandb_context = get_wandb_api_context()

        transport = AIOHTTPTransport(
            url="https://api.wandb.ai/graphql",
            client_session_args={
                "connector": self.connector,
                "connector_owner": False,
            },
            headers=wandb_context.headers,
            cookies=wandb_context.cookies,
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


async def get_wandb_api() -> WandbApiAsync:
    return WandbApiAsync()
