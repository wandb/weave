import os
from . import graph_client
from . import graph_client_local
from . import graph_client_wandb_art_st
from .trace_server import graph_client_trace, remote_http_trace_server
from . import context_state
from . import errors
from . import autopatch
from .chobj import chobj
from . import weave_client


class InitializedClient:
    def __init__(self, client: graph_client.GraphClient):
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


def init_chobj() -> InitializedClient:
    # entity_name, project_name = get_entity_project_from_project_name(project_name)
    client = chobj.ObjectClient()

    init_client = InitializedClient(client)  # type: ignore

    # autopatching is only supporte for the wandb client, because OpenAI calls are not
    # logged in local mode currently. When that's fixed, this autopatch call can be
    # moved to InitializedClient.__init__
    autopatch.autopatch()

    return init_client


def init_weave(project_name: str) -> InitializedClient:
    from . import wandb_api

    # entity_name, project_name = get_entity_project_from_project_name(project_name)
    entity_name, project_name = project_name.split("/", 1)

    remote_server = remote_http_trace_server.RemoteHTTPTraceServer.from_env(True)
    # from .trace_server.clickhouse_trace_server_batched import ClickHouseTraceServer

    wandb_context = wandb_api.get_wandb_api_context()
    if wandb_context is not None and wandb_context.api_key is not None:
        remote_server.set_auth(("api", wandb_context.api_key))

    # server = ClickHouseTraceServer(host="localhost")
    client = weave_client.WeaveClient(entity_name, project_name, remote_server)

    init_client = InitializedClient(client)
    # entity_name, project_name = get_entity_project_from_project_name(project_name)
    # from .trace_server.clickhouse_trace_server_batched import ClickHouseTraceServer

    # client = weave_client.WeaveClient(ClickHouseTraceServer(host="localhost"))

    # init_client = InitializedClient(client)  # type: ignore

    # autopatching is only supporte for the wandb client, because OpenAI calls are not
    # logged in local mode currently. When that's fixed, this autopatch call can be
    # moved to InitializedClient.__init__
    autopatch.autopatch()

    return init_client


def init_wandb(project_name: str) -> InitializedClient:
    entity_name, project_name = get_entity_project_from_project_name(project_name)
    client = graph_client_wandb_art_st.GraphClientWandbArtStreamTable(
        entity_name, project_name
    )

    init_client = InitializedClient(client)

    # autopatching is only supporte for the wandb client, because OpenAI calls are not
    # logged in local mode currently. When that's fixed, this autopatch call can be
    # moved to InitializedClient.__init__
    autopatch.autopatch()

    return init_client


def init_local() -> InitializedClient:
    client = graph_client_local.GraphClientLocal()
    return InitializedClient(client)


def init_trace_remote(project_name: str) -> InitializedClient:
    from . import wandb_api

    wandb_api.init()

    entity_name, project_name = get_entity_project_from_project_name(project_name)

    remote_server = remote_http_trace_server.RemoteHTTPTraceServer.from_env(True)
    wandb_context = wandb_api.get_wandb_api_context()
    if wandb_context is not None and wandb_context.api_key is not None:
        remote_server.set_auth(("api", wandb_context.api_key))

    client = graph_client_trace.GraphClientTraceWithArtifactStorage(
        entity_name, project_name, remote_server
    )

    init_client = InitializedClient(client)

    # autopatching is only supporte for the wandb client, because OpenAI calls are not
    # logged in local mode currently. When that's fixed, this autopatch call can be
    # moved to InitializedClient.__init__
    autopatch.autopatch()

    return init_client
