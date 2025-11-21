# Official interface for interacting with the W&B API. All
# Weave interactions with the Weave API should go through this
# module.

# NOTE: This was copied from the query service and contains way more than it needs to.

import logging
from typing import Any

import gql
import graphql
import httpx

from weave.trace import env
from weave.wandb_interface.context import get_wandb_api_context

logger = logging.getLogger(__name__)


class Api:
    def query(self, query: graphql.DocumentNode, **kwargs: Any) -> Any:
        from gql.transport.httpx import HTTPXTransport

        wandb_context = get_wandb_api_context()
        headers = {}
        cookies = None
        auth = None
        if wandb_context is not None:
            if wandb_context.headers:
                headers.update(wandb_context.headers)
            cookies = wandb_context.cookies
            if wandb_context.api_key is not None:
                auth = httpx.BasicAuth("api", wandb_context.api_key)
        url_base = env.wandb_base_url()
        transport = HTTPXTransport(
            url=url_base + "/graphql",
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
        session = client.connect_sync()  # type: ignore
        return session.execute(query, variable_values=kwargs)

    SERVER_INFO_QUERY = gql.gql(
        """
        query ServerInfo {
            serverInfo {
            frontendHost
            }
        }
        """
    )

    def server_info(self) -> Any:
        return self.query(self.SERVER_INFO_QUERY)

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
                            directUrl
                        }
                    }
                }
            }
        }
        """
    )

    def artifact_manifest_url(
        self, entity_name: str, project_name: str, name: str
    ) -> str | None:
        try:
            result = self.query(
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

    ARTIFACT_MANIFEST_FROM_ID_QUERY = gql.gql(
        """
        query ArtifactManifestFromID(
            $artifactID: ID!
        ) {
            artifact(id: $artifactID) {
                currentManifest {
                    id
                    file {
                        directUrl
                    }
                }
            }
        }
        """
    )

    def artifact_manifest_url_from_id(self, art_id: str) -> str | None:
        try:
            result = self.query(self.ARTIFACT_MANIFEST_FROM_ID_QUERY, artifactID=art_id)
        except gql.transport.exceptions.TransportQueryError as e:
            return None
        artifact = result["artifact"]
        if artifact is None:
            return None
        current_manifest = artifact["currentManifest"]
        if current_manifest is None:
            return None
        file = current_manifest["file"]
        if file is None:
            return None
        return file["directUrl"]

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

    def default_entity_name(self) -> str | None:
        try:
            result = self.query(self.VIEWER_DEFAULT_ENTITY_QUERY)
        except gql.transport.exceptions.TransportQueryError as e:
            return None
        try:
            return result.get("viewer", {}).get("defaultEntity", {}).get("name", None)
        except AttributeError:
            return None

    def username(self) -> str | None:
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
        description: str | None = None,
        entity: str | None = None,
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

    PROJECT_QUERY = gql.gql(
        """
        query Project($name: String!, $entityName: String!) {
            project(name: $name, entityName: $entityName) {
                name
            }
        }
        """
    )

    def project(self, entity: str, name: str) -> dict[str, Any]:
        return self.query(self.PROJECT_QUERY, entityName=entity, name=name)


class ApiAsync:
    def __init__(self) -> None:
        import aiohttp

        self.connector = aiohttp.TCPConnector(limit=50)

    async def query(self, query: graphql.DocumentNode, **kwargs: Any) -> Any:
        import aiohttp
        from gql.transport.aiohttp import AIOHTTPTransport

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
        result = await session.execute(query, variable_values=kwargs)
        # Manually reset the connection, bypassing the SSL bug, avoiding ERROR:asyncio:Unclosed client session
        await transport.session.close()
        return result

    SERVER_INFO_QUERY = gql.gql(
        """
        query ServerInfo {
            serverInfo {
            frontendHost
            }
        }
        """
    )

    async def server_info(self) -> Any:
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
    ) -> str | None:
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

    ARTIFACT_MANIFEST_FROM_ID_QUERY = gql.gql(
        """
        query ArtifactManifestFromID(
            $artifactID: ID!
        ) {
            artifact(id: $artifactID) {
                currentManifest {
                    id
                    file {
                        directUrl
                    }
                }
            }
        }
        """
    )

    async def artifact_manifest_url_from_id(self, art_id: str) -> str | None:
        try:
            result = await self.query(
                self.ARTIFACT_MANIFEST_FROM_ID_QUERY, artifactID=art_id
            )
        except gql.transport.exceptions.TransportQueryError as e:
            return None
        artifact = result["artifact"]
        if artifact is None:
            return None
        current_manifest = artifact["currentManifest"]
        if current_manifest is None:
            return None
        file = current_manifest["file"]
        if file is None:
            return None
        return file["directUrl"]

    VIEWER_DEFAULT_ENTITY_QUERY = gql.gql(
        """
        query DefaultEntity {
            viewer {
                defaultEntity {
                    name
                }
            }
        }
        """
    )

    async def default_entity_name(self) -> str | None:
        try:
            result = await self.query(self.VIEWER_DEFAULT_ENTITY_QUERY)
        except gql.transport.exceptions.TransportQueryError as e:
            return None
        try:
            return result.get("viewer", {}).get("defaultEntity", {}).get("name", None)
        except AttributeError:
            return None

    ENTITY_ACCESS_QUERY = gql.gql(
        """
        query Entity($entityName: String!) {
            viewer { username }
            entity(name: $entityName) { readOnly }
        }
        """
    )

    async def can_access_entity(self, entity: str, api_key: str | None) -> bool:
        try:
            result = await self.query(
                self.ENTITY_ACCESS_QUERY, entityName=entity, api_key=api_key
            )
        except gql.transport.exceptions.TransportQueryError as e:
            return False
        return (
            result.get("viewer")
            and result.get("entity", {}).get("readOnly", True) == False
        )
