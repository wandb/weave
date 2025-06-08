import asyncio
import logging
from functools import lru_cache

import aiohttp
from gql import Client, gql
from gql.transport.requests import RequestsHTTPTransport

logger = logging.getLogger(__name__)


def get_internal_service_token() -> str:
    try:
        internal_service_token = (
            "qa-test-service:lillies_FELINES_obtuse_SERENDIPITY_chase"
        )
        # internal_service_token = "weave-worker:9wEl,Iw2jWy4>FCG|ftZkDlG-:q;yLN#"
        # internal_service_token = os.environ["WANDB_INTERNAL_SERVICE_TOKEN"]
    except KeyError:
        raise KeyError("WANDB_INTERNAL_SERVICE_TOKEN is not set")

    return internal_service_token


INTERNAL_SERVICE_TOKEN_PREFIX = "X-Wandb-Internal-Service"


def get_authenticated_client(impersonate_as: str | None = None) -> Client:
    try:
        wandb_base_url = "https://api.qa.wandb.ai"
        # wandb_base_url = os.environ["WANDB_BASE_URL"]
    except KeyError:
        raise KeyError("WANDB_BASE_URL is not set")

    internal_service_token = get_internal_service_token()

    headers = {
        "Authorization": f"{INTERNAL_SERVICE_TOKEN_PREFIX} {internal_service_token}"
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


@lru_cache(maxsize=1000)
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


@lru_cache(maxsize=1000)
def get_username_from_user_id(user_id: str) -> str:
    client = get_authenticated_client()

    payload = client.execute(GET_USERNAME_FROM_USER_ID_QUERY, {"userId": user_id})

    return payload.get("user", {}).get("username")


async def get_completion(
    system_prompt: str, scoring_prompt: str, model: str, project_id: str, user_id: str
) -> str:
    entity_name, project_name = get_external_project_id(project_id)
    username = get_username_from_user_id(user_id)

    try:
        trace_server_base_url = "https://trace_server.wandb.test"
        # trace_server_base_url = os.environ["TRACE_SERVER_BASE_URL"]
    except KeyError:
        raise KeyError("TRACE_SERVER_BASE_URL is not set")

    inputs = {
        "model": model,
        "max_tokens": 1024,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": scoring_prompt},
        ],
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(
            f"{trace_server_base_url}/completions/create",
            json={
                "inputs": inputs,
                "model": model,
                "project_id": f"{entity_name}/{project_name}",
                "track_llm_call": False,
            },
            headers={
                "Wandb-Internal-Service": f"{INTERNAL_SERVICE_TOKEN_PREFIX} {get_internal_service_token()}",
                "impersonated-username": username,
                # Og== is the base64 encoding of ":"
                "Authorization": "Basic Og==",
            },
            ssl=False,
        ) as response:
            return await response.json()


if __name__ == "__main__":
    result = asyncio.run(
        get_completion(
            system_prompt="you are a helpful assistant",
            scoring_prompt="say hello",
            model="claude-sonnet-4-20250514",
            project_id="UHJvamVjdEludGVybmFsSWQ6NDI3NQ==",
            user_id="VXNlcjo5Njc=",
        )
    )
    print(result)
