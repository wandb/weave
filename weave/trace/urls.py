from urllib.parse import quote

from wandb import util as wb_util

from weave.trace import env

BROWSE3_PATH = "browse3"
WEAVE_SLUG = "weave"


def remote_project_root_url(entity_name: str, project_name: str) -> str:
    return (
        f"{wb_util.app_url(env.wandb_base_url())}/{entity_name}/{quote(project_name)}"
    )


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
    return f"{remote_project_root_url(entity_name, project_name)}/r/call/{call_id}"
