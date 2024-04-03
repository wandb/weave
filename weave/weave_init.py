import typing
from . import init_message
from .trace_server import remote_http_trace_server, sqlite_trace_server
from . import context_state
from . import errors
from . import autopatch
from . import weave_client
from . import trace_sentry


class InitializedClient:
    def __init__(self, client: weave_client.WeaveClient):
        self.client = client
        self.graph_client_token = context_state._graph_client.set(client)
        self.ref_tracking_token = context_state._ref_tracking_enabled.set(True)
        self.eager_mode_token = context_state._eager_mode.set(True)
        self.serverless_io_service_token = context_state._serverless_io_service.set(
            True
        )

    def reset(self) -> None:
        context_state._graph_client.reset(self.graph_client_token)
        context_state._ref_tracking_enabled.reset(self.ref_tracking_token)
        context_state._eager_mode.reset(self.eager_mode_token)
        context_state._serverless_io_service.reset(self.serverless_io_service_token)


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
            raise errors.WeaveWandbAuthenticationException(
                'weave init requires wandb. Run "wandb login"'
            )
        project_name = fields[0]
    elif len(fields) == 2:
        entity_name, project_name = fields
    else:
        raise ValueError(
            'project_name must be of the form "<project_name>" or "<entity_name>/<project_name>"'
        )
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


def init_weave(
    project_name: str, ensure_project_exists: bool = True
) -> InitializedClient:
    from . import wandb_api

    # Must init to read ensure we've read auth from the environment, in
    # case we're on a new thread.
    wandb_api.init()
    wandb_context = wandb_api.get_wandb_api_context()
    if wandb_context is None:
        import wandb

        print("Please login to Weights & Biases (https://wandb.ai/) to continue:")
        wandb.login(anonymous="never", force=True)
        wandb_api.init()
        wandb_context = wandb_api.get_wandb_api_context()

    api_key = None
    if wandb_context is not None and wandb_context.api_key is not None:
        api_key = wandb_context.api_key
    remote_server = init_weave_get_server(api_key)
    # from .trace_server.clickhouse_trace_server_batched import ClickHouseTraceServer

    entity_name, project_name = get_entity_project_from_project_name(project_name)

    # server = ClickHouseTraceServer(host="localhost")
    client = weave_client.WeaveClient(
        entity_name, project_name, remote_server, ensure_project_exists
    )

    init_client = InitializedClient(client)
    # entity_name, project_name = get_entity_project_from_project_name(project_name)
    # from .trace_server.clickhouse_trace_server_batched import ClickHouseTraceServer

    # client = weave_client.WeaveClient(ClickHouseTraceServer(host="localhost"))

    # init_client = InitializedClient(client)  # type: ignore

    # autopatching is only supporte for the wandb client, because OpenAI calls are not
    # logged in local mode currently. When that's fixed, this autopatch call can be
    # moved to InitializedClient.__init__
    autopatch.autopatch()

    username = get_username()
    try:
        min_required_version = (
            remote_server.server_info().min_required_weave_python_version
        )
    # TODO: Tighten this exception to only catch the specific exception
    # that is thrown by the server_info call.
    except Exception:
        # Set to a minimum version that will always pass the check
        # In the future, we may want to throw here.
        min_required_version = "0.0.0"
    init_message.assert_min_weave_version(min_required_version)
    init_message.print_init_message(
        username, entity_name, project_name, read_only=not ensure_project_exists
    )

    user_context = {"username": username} if username else None
    trace_sentry.global_trace_sentry.configure_scope(
        {
            "entity_name": entity_name,
            "project_name": project_name,
            "user": user_context,
        }
    )

    return init_client


def init_weave_get_server(
    api_key: typing.Optional[str] = None,
) -> remote_http_trace_server.RemoteHTTPTraceServer:
    res = remote_http_trace_server.RemoteHTTPTraceServer.from_env(True)
    if api_key is not None:
        res.set_auth(("api", api_key))
    return res


def init_local() -> InitializedClient:
    server = sqlite_trace_server.SqliteTraceServer("weave.db")
    server.setup_tables()
    client = weave_client.WeaveClient("none", "none", server)
    return InitializedClient(client)
