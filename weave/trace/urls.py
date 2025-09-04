from urllib.parse import quote

from weave.trace import env

BROWSE3_PATH = "browse3"
WEAVE_SLUG = "weave"


def project_weave_root_url(entity: str, project: str) -> str:
    """Get the frontend URL for viewing a Weave project.

    Args:
        entity: The entity/organization name
        project: The project name

    Returns:
        The frontend URL for viewing the project in Weave
    """
    # Get the appropriate frontend URL (respects WF_TRACE_SERVER_URL if set)
    base_url = env.weave_frontend_url()
    entity = quote(entity)
    project = quote(project)

    return f"{base_url}/{entity}/{project}/{WEAVE_SLUG}"


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
