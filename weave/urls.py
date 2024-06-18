from urllib.parse import quote

from wandb import util as wb_util

from weave.legacy import context_state

from . import environment

BROWSE3_PATH = "browse3"
WEAVE_SLUG = "weave"


def remote_project_root_url(entity_name: str, project_name: str) -> str:
    return f"{wb_util.app_url(environment.wandb_base_url())}/{entity_name}/{quote(project_name)}"


def remote_project_weave_root_url(entity_name: str, project_name: str) -> str:
    return f"{remote_project_root_url(entity_name, project_name)}/{WEAVE_SLUG}"


def local_project_weave_root_url(entity_name: str, project_name: str) -> str:
    return f"http://localhost:3000/{BROWSE3_PATH}/{entity_name}/{quote(project_name)}"


def project_weave_root_url(entity_name: str, project_name: str) -> str:
    if context_state._use_local_urls.get():
        return local_project_weave_root_url(entity_name, project_name)
    else:
        return remote_project_weave_root_url(entity_name, project_name)


def op_version_path(
    entity_name: str, project_name: str, op_name: str, op_version: str
) -> str:
    return f"{project_weave_root_url(entity_name, project_name)}/ops/{op_name}/versions/{op_version}"


def object_version_path(
    entity_name: str, project_name: str, object_name: str, obj_version: str
) -> str:
    return f"{project_weave_root_url(entity_name, project_name)}/objects/{quote(object_name)}/versions/{obj_version}"


def call_path(entity_name: str, project_name: str, call_id: str) -> str:
    return f"{project_weave_root_url(entity_name, project_name)}/calls/{call_id}"


def redirect_call(entity_name: str, project_name: str, call_id: str) -> str:
    return f"{remote_project_root_url(entity_name, project_name)}/r/call/{call_id}"


def use_local_urls() -> None:
    context_state._use_local_urls.set(True)


def use_remote_urls() -> None:
    context_state._use_local_urls.set(False)
