import os
from urllib.parse import quote, urlparse

from weave.compat import wandb
from weave.trace import env

BROWSE3_PATH = "browse3"
WEAVE_SLUG = "weave"


def remote_project_root_url(entity_name: str, project_name: str) -> str:
    return f"{wandb.app_url(env.wandb_base_url())}/{entity_name}/{quote(project_name)}"


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
    # Check if WF_TRACE_SERVER_URL is set (indicating local development)
    trace_server_url = os.getenv("WF_TRACE_SERVER_URL")
    if trace_server_url:
        # Parse the trace server URL to extract the base URL
        parsed = urlparse(trace_server_url)
        # Use the host and port from the trace server URL
        # Default to localhost:9000 if parsing fails or no host is found
        if parsed.hostname:
            base_url = f"{parsed.scheme or 'http'}://{parsed.hostname}"
            if parsed.port:
                base_url += f":{parsed.port}"
        else:
            # Fallback to localhost:9000 if we can't parse the URL properly
            base_url = "http://localhost:9000"
        return f"{base_url}/{entity_name}/{quote(project_name)}/{WEAVE_SLUG}/r/call/{call_id}"

    # Default behavior: use the remote project root URL
    return f"{remote_project_root_url(entity_name, project_name)}/r/call/{call_id}"
