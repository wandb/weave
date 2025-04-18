from __future__ import annotations

from weave.trace import (
    autopatch,
    init_message,
    trace_sentry,
    wandb_termlog_patch,
    weave_client,
)
from weave.trace.context import weave_client_context as weave_client_context
from weave.trace.settings import should_redact_pii, use_server_cache
from weave.trace_server.trace_server_interface import TraceServerInterface
from weave.trace_server_bindings import remote_http_trace_server
from weave.trace_server_bindings.caching_middleware_trace_server import (
    CachingMiddlewareTraceServer,
)


class InitializedClient:
    def __init__(self, client: weave_client.WeaveClient):
        self.client = client
        weave_client_context.set_weave_client_global(client)

    def reset(self) -> None:
        weave_client_context.set_weave_client_global(None)


_current_inited_client: InitializedClient | None = None


def get_username() -> str | None:
    from weave.wandb_interface import wandb_api

    api = wandb_api.get_wandb_api_sync()
    try:
        return api.username()
    except AttributeError:
        return None


class WeaveWandbAuthenticationException(Exception): ...


def get_entity_project_from_project_name(project_name: str) -> tuple[str, str]:
    from weave.wandb_interface import wandb_api

    fields = project_name.split("/")
    if len(fields) == 1:
        api = wandb_api.get_wandb_api_sync()
        entity_name = api.default_entity_name()
        if entity_name is None:
            raise WeaveWandbAuthenticationException(
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
    ensure_project_exists (bool): If True (default), the client will attempt to create the project if it does not exist.
"""


def init_weave(
    project_name: str,
    ensure_project_exists: bool = True,
    autopatch_settings: autopatch.AutopatchSettings | None = None,
) -> InitializedClient:
    global _current_inited_client
    if _current_inited_client is not None:
        # TODO: Prob should move into settings
        if (
            _current_inited_client.client.project == project_name
            and _current_inited_client.client.ensure_project_exists
            == ensure_project_exists
        ):
            return _current_inited_client
        else:
            _current_inited_client.reset()

    from weave.wandb_interface import wandb_api  # type: ignore

    # Must init to read ensure we've read auth from the environment, in
    # case we're on a new thread.
    wandb_api.init()
    wandb_context = wandb_api.get_wandb_api_context()
    if wandb_context is None:
        import wandb

        print("Please login to Weights & Biases (https://wandb.ai/) to continue:")
        wandb_termlog_patch.ensure_patched()
        wandb.login(anonymous="never", force=True)  # type: ignore
        wandb_api.init()
        wandb_context = wandb_api.get_wandb_api_context()

    entity_name, project_name = get_entity_project_from_project_name(project_name)
    wandb_run_id = weave_client.safe_current_wb_run_id()
    weave_client.check_wandb_run_matches(wandb_run_id, entity_name, project_name)

    api_key = None
    if wandb_context is not None and wandb_context.api_key is not None:
        api_key = wandb_context.api_key

    remote_server = init_weave_get_server(api_key)
    server: TraceServerInterface = remote_server
    if use_server_cache():
        server = CachingMiddlewareTraceServer.from_env(server)

    client = weave_client.WeaveClient(
        entity_name, project_name, server, ensure_project_exists
    )

    # If the project name was formatted by init, update the project name
    project_name = client.project

    _current_inited_client = InitializedClient(client)

    # autopatching is only supported for the wandb client, because OpenAI calls are not
    # logged in local mode currently. When that's fixed, this autopatch call can be
    # moved to InitializedClient.__init__
    autopatch.autopatch(autopatch_settings)

    username = get_username()

    # This is a temporary event to track the number of users who have enabled PII redaction.
    if should_redact_pii():
        from weave.trace.pii_redaction import track_pii_redaction_enabled

        track_pii_redaction_enabled(username or "unknown", entity_name, project_name)

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

    return _current_inited_client


def init_weave_disabled() -> InitializedClient:
    """Initialize a dummy client that does nothing.

    This is used when the program is execuring with Weave disabled.

    Note: as currently implemented, any explicit calls to client.{X} will
    likely fail, since the user is not authenticated. The purpose of
    disabling weave is to disable _tracing_. Programs that attempt to
    make requests (eg. publishing, fetching, querying) while disabled
    will fail.
    """
    global _current_inited_client
    if _current_inited_client is not None:
        _current_inited_client.reset()

    client = weave_client.WeaveClient(
        "DISABLED",
        "DISABLED",
        init_weave_get_server("DISABLED", should_batch=False),
        ensure_project_exists=False,
    )

    return InitializedClient(client)


def init_weave_get_server(
    api_key: str | None = None,
    should_batch: bool = True,
) -> remote_http_trace_server.RemoteHTTPTraceServer:
    res = remote_http_trace_server.RemoteHTTPTraceServer.from_env(should_batch)
    if api_key is not None:
        res.set_auth(("api", api_key))
    return res


def init_local() -> InitializedClient:
    from weave.trace_server import sqlite_trace_server

    server = sqlite_trace_server.SqliteTraceServer("weave.db")
    server.setup_tables()
    client = weave_client.WeaveClient("none", "none", server)
    return InitializedClient(client)


def finish() -> None:
    global _current_inited_client
    if _current_inited_client is not None:
        _current_inited_client.reset()
        _current_inited_client = None

    # autopatching is only supported for the wandb client, because OpenAI calls are not
    # logged in local mode currently. When that's fixed, this reset_autopatch call can be
    # moved to InitializedClient.reset
    autopatch.reset_autopatch()
    trace_sentry.global_trace_sentry.end_session()
