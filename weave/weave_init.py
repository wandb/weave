import typing
from . import graph_client
from . import graph_client_local
from . import graph_client_wandb_art_st
from . import context_state
from . import errors
from . import autopatch


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


def init_wandb(project_name: str) -> InitializedClient:
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
