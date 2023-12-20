import urllib
import json
from wandb import util as wb_util

from . import environment
from . import context_state

BROWSE3_PATH = "browse3"
WORKSPACE_SLUG = "weaveflow"


def remote_project_root_url(entity_name: str, project_name: str) -> str:
    return f"{wb_util.app_url(environment.wandb_base_url())}/{entity_name}/{project_name}/{WORKSPACE_SLUG}"


def local_project_root_url(entity_name: str, project_name: str) -> str:
    return f"http://localhost:3000/{BROWSE3_PATH}/{entity_name}/{project_name}"


def project_root_url(entity_name: str, project_name: str) -> str:
    if context_state._use_local_urls.get():
        return local_project_root_url(entity_name, project_name)
    else:
        return remote_project_root_url(entity_name, project_name)


def project_path(entity_name: str, project_name: str) -> str:
    return f"{project_root_url(entity_name, project_name)}"


def op_version_path(
    entity_name: str, project_name: str, op_name: str, op_version: str
) -> str:
    return f"{project_root_url(entity_name, project_name)}/ops/{op_name}/versions/{op_version}"


def object_version_path(
    entity_name: str, project_name: str, object_name: str, op_version: str
) -> str:
    return f"{project_root_url(entity_name, project_name)}/objects/{object_name}/versions/{op_version}"


def call_path(entity_name: str, project_name: str, call_id: str) -> str:
    return f"{project_root_url(entity_name, project_name)}/calls/{call_id}"


def call_path_as_peek(entity_name: str, project_name: str, call_id: str) -> str:
    return f"{call_path(entity_name, project_name, call_id)}?convertToPeek=true"


def use_local_urls() -> None:
    context_state._use_local_urls.set(True)


def use_remote_urls() -> None:
    context_state._use_local_urls.set(False)
