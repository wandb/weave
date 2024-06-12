import typing

from . import autopatch, context_state, errors, init_message, trace_sentry, weave_client
from .trace_server import remote_http_trace_server, sqlite_trace_server

_current_inited_client = None


def get_username() -> typing.Optional[str]:
    from . import wandb_api

    api = wandb_api.get_wandb_api_sync()
    try:
        return api.username()
    except AttributeError:
        return None


def get_entity_project_from_project_name(project_name: str) -> tuple[str, str]:
    from . import wandb_api

    fields = project_name.split("/")
    if len(fields) == 1:
        api = wandb_api.get_wandb_api_sync()
        try:
            entity_name = api.default_entity_name()
        except AttributeError:
            raise errors.WeaveWandbAuthenticationException('weave init requires wandb. Run "wandb login"')
        project_name = fields[0]
    elif len(fields) == 2:
        entity_name, project_name = fields
    else:
        raise ValueError('project_name must be of the form "<project_name>" or "<entity_name>/<project_name>"')
    if not entity_name:
        raise ValueError("entity_name must be non-empty")

    return entity_name, project_name


"""
This is the main entrypoint for the weave library. It initializes the weave client
and sets up the global state for the weave library.

Args:
    project_name (str): The project name to use for the weave client.
    ensure_project_exists (bool): If True, the client will not attempt to create the project
"""


def init_weave_get_server(
    api_key: typing.Optional[str] = None,
) -> remote_http_trace_server.RemoteHTTPTraceServer:
    res = remote_http_trace_server.RemoteHTTPTraceServer.from_env(True)
    if api_key is not None:
        res.set_auth(("api", api_key))
    return res
