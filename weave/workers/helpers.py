import logging
import os
from typing import Optional

import aiohttp
from cachetools import TLRUCache, cached
from gql import Client, gql
from gql.transport.requests import RequestsHTTPTransport

from weave.trace_server.trace_server_interface import (
    CompletionsCreateReq,
    CompletionsCreateRequestInputs,
    CompletionsCreateRes,
)

logger = logging.getLogger(__name__)


def get_internal_service_token() -> str:
    try:
        internal_service_token = os.environ["WANDB_INTERNAL_SERVICE_TOKEN"]
        secret_name = os.environ["WANDB_INTERNAL_SERVICE_TOKEN_SECRET_NAME"]
    except KeyError:
        raise KeyError("WANDB_INTERNAL_SERVICE_TOKEN is not set")

    return f"{secret_name}:{internal_service_token}"


INTERNAL_SERVICE_TOKEN_PREFIX = "X-Wandb-Internal-Service"


def get_authenticated_client(impersonate_as: Optional[str] = None) -> Client:
    try:
        wandb_base_url = os.environ["WANDB_BASE_URL"]
    except KeyError:
        raise KeyError("WANDB_BASE_URL is not set")

    internal_service_token = get_internal_service_token()

    headers = {
        "Authorization": f"{INTERNAL_SERVICE_TOKEN_PREFIX} {internal_service_token}",
        # "X-Wandb-Force-Trace": "true",
    }
    if impersonate_as:
        headers["impersonated-username"] = impersonate_as

    transport = RequestsHTTPTransport(
        f"{wandb_base_url}/graphql",
        headers=headers,
    )

    return Client(transport=transport)


CONVERT_INT_TO_EXT_PROJECT_ID_PARTS_QUERY = gql(
    """
        query WeaveWorkerProjectIdToNames ($internalId: ID!) {
            project(internalId: $internalId) {
                name
                entity {
                    name
                }
            }
        }
    """
)


@cached(cache=TLRUCache(maxsize=1000, ttu=lambda key, value, now: now + 600))
def get_external_project_id(project_id: str) -> tuple[str, str]:
    client = get_authenticated_client()
    logger.info(f"Querying Gorilla for external project ID for {project_id} ")
    payload = client.execute(
        CONVERT_INT_TO_EXT_PROJECT_ID_PARTS_QUERY, {"internalId": project_id}
    )
    project_payload = payload.get("project", {})
    project_name = project_payload.get("name")
    entity_payload = project_payload.get("entity", {})
    entity_name = entity_payload.get("name")

    if not project_name or not entity_name:
        raise ValueError(f"Project with internal ID {project_id} not found")

    return entity_name, project_name


GET_USERNAME_FROM_USER_ID_QUERY = gql(
    """
        query WeaveWorkerUserIdToUsername ($userId: ID!) {
            user(id: $userId) {
                username
            }
        }
    """
)


@cached(cache=TLRUCache(maxsize=1000, ttu=lambda key, value, now: now + 600))
def get_username_from_user_id(user_id: str) -> str:
    client = get_authenticated_client()

    payload = client.execute(GET_USERNAME_FROM_USER_ID_QUERY, {"userId": user_id})

    return payload.get("user", {}).get("username")


async def get_completion(
    request: CompletionsCreateReq, user_id: str
) -> CompletionsCreateRes:
    username = get_username_from_user_id(user_id)
    try:
        trace_server_base_url = os.environ["WEAVE_TRACE_SERVER_BASE_URL"]
    except KeyError:
        raise KeyError("WEAVE_TRACE_SERVER_BASE_URL is not set")

    async with aiohttp.ClientSession() as session:
        async with session.post(
            f"{trace_server_base_url}/completions/create",
            json=request.model_dump(),
            headers={
                # This is for Gorilla to authenticate the request
                "Wandb-Internal-Service": f"{INTERNAL_SERVICE_TOKEN_PREFIX} {get_internal_service_token()}",
                "impersonated-username": username,
                # Og== is the base64 encoding of ":"
                # This is required for the trace server to accept the request
                "Authorization": "Basic Og==",
            },
            ssl=False,
        ) as response:
            return CompletionsCreateRes.model_validate(await response.json())


# EVERYTHING BELOW THIS LINE IS FOR TESTING PURPOSES ONLY
# WILL BE YANKED BEFORE MERGING


def get_permissions() -> None:
    client = get_authenticated_client()
    payload = client.execute(
        gql(
            """
        query CanReadProjectScope($projectName: String, $entityName: String) {
            project(name: $projectName, entityName: $entityName) {
                internalId
                weavePermissions {
                    canRead
                    canWrite
                }
            }
        }
    """
        ),
        {"projectName": "monitor-test", "entityName": "wandb"},
        # {
        #    "projectName": "performance-tests",
        #    "entityName": "artifacts-sdk-tests",
        # },
    )
    print(payload)


def ext_to_int_project_id() -> None:
    client = get_authenticated_client()
    payload = client.execute(
        gql(
            """
        query WeaveTraceServerProjectNamesToId ($entityName: String, $projectName: String) {
            project(name: $projectName, entityName: $entityName) {
                internalId
            }
        }
    """
        ),
        {"entityName": "wandb", "projectName": "monitor-test"},
        # {"entityName": "weave-team", "projectName": "monitor-test"},
        # {"entityName": "artifacts-sdk-tests", "projectName": "performance-tests"},
    )
    print(payload)


if __name__ == "__main__":
    req = CompletionsCreateReq(
        project_id="wandb/monitor-test",
        track_llm_call=False,
        inputs=CompletionsCreateRequestInputs(
            model="claude-sonnet-4-20250514",
            messages=[
                {
                    "role": "user",
                    "content": "say hello",
                }
            ],
        ),
    )
    # result = asyncio.run(get_completion(req, "VXNlcjoyMzU4MjI0"))
    # print(result)
    logging.basicConfig(level=logging.DEBUG)
    # print(get_permissions())
    # print(ext_to_int_project_id())
    # print(get_username_from_user_id("VXNlcjo5Njc="))
    # print(get_username_from_user_id("VXNlcjo2Mzg4Nw=="))
    # print(get_username_from_user_id("VXNlcjoyMzU4MjI0"))
    # print(get_external_project_id("UHJvamVjdEludGVybmFsSWQ6NDI3NQ=="))
