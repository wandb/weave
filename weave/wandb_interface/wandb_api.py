# Official interface for interacting with the W&B API. All
# Weave interactions with the Weave API should go through this
# module.

# NOTE: This was copied from the query service and contains way more than it needs to.

import contextvars
import dataclasses
from typing import Any, Optional

import aiohttp
import gql
import graphql
from gql.transport.aiohttp import AIOHTTPTransport
from gql.transport.requests import RequestsHTTPTransport
from requests.auth import HTTPBasicAuth

try:
    from wandb.sdk.internal.internal_api import _thread_local_api_settings
except ImportError:
    WANDB_AVAILABLE = False
else:
    WANDB_AVAILABLE = True

from weave.trace import env


# Context for wandb api
# Instead of putting this in a shared file, we put it directly here
# so that the patching at the top of this file will work correctly
# for this symbol.
@dataclasses.dataclass
class WandbApiContext:
    user_id: Optional[str] = None  # TODO: delete
    api_key: Optional[str] = None
    headers: Optional[dict[str, str]] = None  # TODO: delete
    cookies: Optional[dict[str, str]] = None  # TODO: delete

    @classmethod
    def from_json(cls, json: Any) -> "WandbApiContext":
        return cls(**json)

    def to_json(self) -> Any:
        return dataclasses.asdict(self)


## wandb_api.py context
_wandb_api_context: contextvars.ContextVar[Optional[WandbApiContext]] = (
    contextvars.ContextVar("wandb_api_context", default=None)
)


def set_wandb_thread_local_api_settings(
    api_key: Optional[str],
    cookies: Optional[dict],
    headers: Optional[dict],
) -> None:
    if WANDB_AVAILABLE:
        _thread_local_api_settings.api_key = api_key
        _thread_local_api_settings.cookies = cookies
        _thread_local_api_settings.headers = headers


def set_wandb_api_context(
    user_id: Optional[str],
    api_key: Optional[str],
    headers: Optional[dict],
    cookies: Optional[dict],
) -> Optional[contextvars.Token[Optional[WandbApiContext]]]:
    cur_ctx = get_wandb_api_context()
    if cur_ctx:
        # WANDB API context is only allowed to be set once per thread, since we
        # need to use thread local storage to communicate the context to the wandb
        # lib right now.
        return None
    set_wandb_thread_local_api_settings(api_key, cookies, headers)
    return _wandb_api_context.set(WandbApiContext(user_id, api_key, headers, cookies))


# api.py, weave_init.py
def get_wandb_api_context() -> Optional[WandbApiContext]:
    return _wandb_api_context.get()


def init() -> Optional[contextvars.Token[Optional[WandbApiContext]]]:
    api_key = env.weave_wandb_api_key()
    if api_key:
        return set_wandb_api_context("admin", api_key, None, None)
    return None


class WandbApiAsync:
    def __init__(self) -> None:
        self.connector = aiohttp.TCPConnector(limit=50)

    async def query(self, query: graphql.DocumentNode, **kwargs: Any) -> Any:
        wandb_context = get_wandb_api_context()
        headers = None
        cookies = None
        auth = None
        if wandb_context is not None:
            headers = wandb_context.headers
            cookies = wandb_context.cookies
            if wandb_context.api_key is not None:
                auth = aiohttp.BasicAuth("api", wandb_context.api_key)
        # TODO: This is currently used by our FastAPI auth helper, there's probably a better way.
        api_key_override = kwargs.pop("api_key", None)
        if api_key_override:
            auth = aiohttp.BasicAuth("api", api_key_override)
        url_base = env.wandb_base_url()
        transport = AIOHTTPTransport(
            url=url_base + "/graphql",
            client_session_args={
                "connector": self.connector,
                "connector_owner": False,
            },
            headers=headers,
            cookies=cookies,
            auth=auth,
        )
        # Warning: we do not use the recommended context manager pattern, because we're
        # using connector_owner to tell the session not to close our connection pool.
        # There is a bug in aiohttp that causes session close to hang for the ssl_close_timeout
        # which is 10 seconds by default. See issue: https://github.com/graphql-python/gql/issues/381
        # Closing the session just closes the connector, which we don't want anyway, so we don't
        # bother.
        client = gql.Client(transport=transport, fetch_schema_from_transport=False)
        session = await client.connect_async(reconnecting=False)  # type: ignore
        result = await session.execute(query, kwargs)
        # Manually reset the connection, bypassing the SSL bug, avoiding ERROR:asyncio:Unclosed client session
        await transport.session.close()
        return result


class WandbApi:
    def query(self, query: graphql.DocumentNode, **kwargs: Any) -> Any:
        wandb_context = get_wandb_api_context()
        headers = None
        cookies = None
        auth = None
        if wandb_context is not None:
            headers = wandb_context.headers
            cookies = wandb_context.cookies
            if wandb_context.api_key is not None:
                auth = HTTPBasicAuth("api", wandb_context.api_key)
        url_base = env.wandb_base_url()
        transport = RequestsHTTPTransport(
            url=url_base + "/graphql", headers=headers, cookies=cookies, auth=auth
        )
        # Warning: we do not use the recommended context manager pattern, because we're
        # using connector_owner to tell the session not to close our connection pool.
        # There is a bug in aiohttp that causes session close to hang for the ssl_close_timeout
        # which is 10 seconds by default. See issue: https://github.com/graphql-python/gql/issues/381
        # Closing the session just closes the connector, which we don't want anyway, so we don't
        # bother.
        client = gql.Client(transport=transport, fetch_schema_from_transport=False)
        session = client.connect_sync()  # type: ignore
        return session.execute(query, kwargs)

    VIEWER_DEFAULT_ENTITY_QUERY = gql.gql(
        """
        query DefaultEntity {
            viewer {
                username
                defaultEntity {
                    name
                }
            }
        }
        """
    )

    def default_entity_name(self) -> Optional[str]:
        try:
            result = self.query(self.VIEWER_DEFAULT_ENTITY_QUERY)
        except gql.transport.exceptions.TransportQueryError as e:
            return None
        try:
            return result.get("viewer", {}).get("defaultEntity", {}).get("name", None)
        except AttributeError:
            return None

    def username(self) -> Optional[str]:
        try:
            result = self.query(self.VIEWER_DEFAULT_ENTITY_QUERY)
        except gql.transport.exceptions.TransportQueryError as e:
            return None

        return result.get("viewer", {}).get("username", None)

    UPSERT_PROJECT_MUTATION = gql.gql(
        """
    mutation UpsertModel($name: String!, $id: String, $entity: String!, $description: String, $repo: String)  {
        upsertModel(input: { id: $id, name: $name, entityName: $entity, description: $description, repo: $repo }) {
            model {
                name
                description
            }
        }
    }
    """
    )

    def upsert_project(
        self,
        project: str,
        description: Optional[str] = None,
        entity: Optional[str] = None,
    ) -> dict[str, Any]:
        """Create a new project.

        Args:
            project (str): The project to create
            description (str, optional): A description of this project
            entity (str, optional): The entity to scope this project to.
        """
        return self.query(
            self.UPSERT_PROJECT_MUTATION,
            name=project,
            entity=entity,
            description=description,
        )


async def get_wandb_api() -> WandbApiAsync:
    return WandbApiAsync()


def get_wandb_api_sync() -> WandbApi:
    return WandbApi()
