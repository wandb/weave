import os
from urllib.parse import quote, urlparse

from weave.trace import env

BROWSE3_PATH = "browse3"
WEAVE_SLUG = "weave"


def _get_base_url() -> str:
    """Get the base URL for frontend navigation.

    Returns the appropriate base URL based on environment:
    - If WF_TRACE_SERVER_URL is set, extract and use its base URL
    - Otherwise, use the standard frontend URL
    """
    trace_server_url = os.getenv("WF_TRACE_SERVER_URL")
    if trace_server_url:
        # Parse the URL to extract base components for frontend navigation
        parsed = urlparse(trace_server_url)
        if parsed.hostname:
            base_url = f"{parsed.scheme or 'http'}://{parsed.hostname}"
            if parsed.port:
                base_url += f":{parsed.port}"
            return base_url
        # Fallback for invalid URLs
        return "http://localhost:9000"

    # Use standard frontend URL
    return env.wandb_frontend_base_url()


def remote_project_root_url(entity_name: str, project_name: str) -> str:
    return f"{_get_base_url()}/{entity_name}/{quote(project_name)}"


def project_weave_root_url(entity_name: str, project_name: str) -> str:
    return f"{remote_project_root_url(entity_name, project_name)}/{WEAVE_SLUG}"


def op_version_path(
    entity_name: str, project_name: str, op_name: str, op_version: str
) -> str:
    return f"{project_weave_root_url(entity_name, project_name)}/ops/{op_name}/versions/{op_version}"


def object_version_path(
    entity_name: str, project_name: str, object_name: str, obj_version: str
) -> str:
    return f"{project_weave_root_url(entity_name, project_name)}/objects/{quote(object_name)}/versions/{obj_version}"


def leaderboard_path(entity_name: str, project_name: str, object_name: str) -> str:
    return f"{project_weave_root_url(entity_name, project_name)}/leaderboards/{quote(object_name)}"


def redirect_call(entity_name: str, project_name: str, call_id: str) -> str:
    return f"{project_weave_root_url(entity_name, project_name)}/r/call/{call_id}"
