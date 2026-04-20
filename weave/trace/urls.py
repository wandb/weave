from urllib.parse import quote

from weave.compat import wandb
from weave.trace import env

BROWSE3_PATH = "browse3"
WEAVE_SLUG = "weave"


def remote_project_root_url(
    entity_name: str,
    project_name: str,
    base_url: str | None = None,
) -> str:
    effective = base_url if base_url is not None else env.wandb_base_url()
    return f"{wandb.app_url(effective)}/{entity_name}/{quote(project_name)}"


def project_weave_root_url(
    entity_name: str,
    project_name: str,
    base_url: str | None = None,
) -> str:
    return f"{remote_project_root_url(entity_name, project_name, base_url=base_url)}/{WEAVE_SLUG}"


def op_version_path(
    entity_name: str,
    project_name: str,
    op_name: str,
    op_version: str,
    base_url: str | None = None,
) -> str:
    return f"{project_weave_root_url(entity_name, project_name, base_url=base_url)}/ops/{op_name}/versions/{op_version}"


def object_version_path(
    entity_name: str,
    project_name: str,
    object_name: str,
    obj_version: str,
    base_url: str | None = None,
) -> str:
    return f"{project_weave_root_url(entity_name, project_name, base_url=base_url)}/objects/{quote(object_name)}/versions/{obj_version}"


def leaderboard_path(
    entity_name: str,
    project_name: str,
    object_name: str,
    base_url: str | None = None,
) -> str:
    return f"{project_weave_root_url(entity_name, project_name, base_url=base_url)}/leaderboards/{quote(object_name)}"


def redirect_call(
    entity_name: str,
    project_name: str,
    call_id: str,
    base_url: str | None = None,
) -> str:
    return f"{remote_project_root_url(entity_name, project_name, base_url=base_url)}/r/call/{call_id}"
