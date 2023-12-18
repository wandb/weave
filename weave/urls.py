import contextvars
import contextlib
import typing

BROWSE3_PATH = "browse3"
LOCAL_BASE_URL = "http://localhost:3000"
WORKSPACE_SLUG = "weaveflow"
REMOTE_BASE_URL = "https://wandb.ai"


def remote_project_root_url(entity_name: str, project_name: str) -> str:
    return f"{REMOTE_BASE_URL}/{entity_name}/{project_name}/{WORKSPACE_SLUG}"


def local_project_root_url(entity_name: str, project_name: str) -> str:
    return f"{LOCAL_BASE_URL}/{BROWSE3_PATH}/{entity_name}/{project_name}"


def project_path(entity_name: str, project_name: str) -> str:
    return f"{_project_root_url_fn.get()(entity_name, project_name)}"


def op_version_path(
    entity_name: str, project_name: str, op_name: str, op_version: str
) -> str:
    return f"{_project_root_url_fn.get()(entity_name, project_name)}/ops/{op_name}/versions/{op_version}"


def object_version_path(
    entity_name: str, project_name: str, object_name: str, op_version: str
) -> str:
    return f"{_project_root_url_fn.get()(entity_name, project_name)}/objects/{object_name}/versions/{op_version}"


def call_path(entity_name: str, project_name: str, call_id: str) -> str:
    return f"{_project_root_url_fn.get()(entity_name, project_name)}/calls/{call_id}"


## URL Context
_project_root_url_fn: contextvars.ContextVar[
    typing.Callable[[str, str], str]
] = contextvars.ContextVar("project_root_url_fn", default=remote_project_root_url)


@contextlib.contextmanager
def set_urls_to_local(key: typing.Optional[str] = None):
    token = _project_root_url_fn.set(local_project_root_url)
    try:
        yield
    finally:
        _project_root_url_fn.reset(token)


@contextlib.contextmanager
def set_urls_to_remote(key: typing.Optional[str] = None):
    token = _project_root_url_fn.set(local_project_root_url)
    try:
        yield
    finally:
        _project_root_url_fn.reset(token)
