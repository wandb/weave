from __future__ import annotations

import logging
import os
from json import JSONDecodeError

from weave.compat import wandb
from weave.telemetry import trace_sentry
from weave.trace import env, init_message, weave_client
from weave.trace.context import weave_client_context as weave_client_context
from weave.trace.settings import (
    should_redact_pii,
    should_use_stainless_server,
    use_server_cache,
)
from weave.trace.wandb_run_context import (
    check_wandb_run_matches,
    get_global_wb_run_context,
)
from weave.trace_server_bindings.caching_middleware_trace_server import (
    CachingMiddlewareTraceServer,
)
from weave.trace_server_bindings.client_interface import TraceServerClientInterface
from weave.trace_server_bindings.remote_http_trace_server import RemoteHTTPTraceServer
from weave.trace_server_version import MIN_TRACE_SERVER_VERSION

logger = logging.getLogger(__name__)


class WeaveWandbAuthenticationException(Exception): ...


def get_username() -> str | None:
    api = wandb.Api()
    try:
        return api.username()
    except AttributeError:
        return None


def get_entity_project_from_project_name(project_name: str) -> tuple[str, str]:
    if not project_name or not project_name.strip():
        raise ValueError("project_name must be non-empty")

    fields = project_name.split("/")
    if len(fields) == 1:
        # First check for WANDB_ENTITY environment variable
        entity_name = os.environ.get("WANDB_ENTITY")
        if entity_name is None:
            # Fall back to wandb default entity
            api = wandb.Api()
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
    if not project_name:
        raise ValueError("project_name must be non-empty")

    return entity_name, project_name


"""
This is the main entrypoint for the weave library. It initializes the weave client
and sets up the global state for the weave library.

Args:
    project_name (str): The project name to use for the weave client.
    ensure_project_exists (bool): If True (default), the client will attempt to create the project if it does not exist.
"""


def _weave_is_available(server: TraceServerClientInterface) -> bool:
    try:
        server.server_info()
    except JSONDecodeError:
        return False
    except Exception:
        logger.warning(
            "Unexpected error when checking if Weave is available on the server.  Please contact support."
        )
        return False
    return True


def init_weave(
    project_name: str,
    ensure_project_exists: bool = True,
) -> weave_client.WeaveClient:
    if not project_name or not project_name.strip():
        raise ValueError("project_name must be non-empty")

    current_client = weave_client_context.get_weave_client()
    if current_client is not None:
        # TODO: Prob should move into settings
        if (
            current_client.project == project_name
            and current_client.ensure_project_exists == ensure_project_exists
        ):
            return current_client
        else:
            # Flush any pending calls before switching to a new project
            current_client.finish()
            weave_client_context.set_weave_client_global(None)

    from weave.wandb_interface import (
        context as wandb_context_module,  # type: ignore
    )

    # Must init to read ensure we've read auth from the environment, in
    # case we're on a new thread.
    wandb_context_module.init()
    wandb_context = wandb_context_module.get_wandb_api_context()
    if wandb_context is None:
        url = wandb.app_url(env.wandb_base_url())
        logger.info(f"Please login to Weights & Biases ({url}) to continue...")
        wandb.login(anonymous="never", force=True, referrer="weave")  # type: ignore

        wandb_context_module.init()
        wandb_context = wandb_context_module.get_wandb_api_context()

    # Resolve entity name after authentication is ensured
    entity_name, project_name = get_entity_project_from_project_name(project_name)
    wb_run_context = get_global_wb_run_context()
    if wb_run_context:
        wandb_run_id = f"{entity_name}/{project_name}/{wb_run_context.run_id}"
        check_wandb_run_matches(wandb_run_id, entity_name, project_name)

    api_key = None
    if wandb_context is not None and wandb_context.api_key is not None:
        api_key = wandb_context.api_key

    remote_server = init_weave_get_server(api_key)
    if not _weave_is_available(remote_server):
        raise RuntimeError(
            "Weave is not available on the server.  Please contact support."
        )
    server: TraceServerClientInterface = remote_server
    if use_server_cache():
        server = CachingMiddlewareTraceServer.from_env(server)

    client = weave_client.WeaveClient(
        entity_name, project_name, server, ensure_project_exists
    )

    # If the project name was formatted by init, update the project name
    project_name = client.project

    weave_client_context.set_weave_client_global(client)

    # Implicit patching:
    # 1. Check sys.modules and automatically patch any already-imported integrations
    # 2. Register import hook to patch integrations imported after weave.init()
    from weave.integrations.patch import implicit_patch, register_import_hook

    implicit_patch()
    register_import_hook()

    username = get_username()

    # This is a temporary event to track the number of users who have enabled PII redaction.
    if should_redact_pii():
        from weave.utils.pii_redaction import track_pii_redaction_enabled

        track_pii_redaction_enabled(username or "unknown", entity_name, project_name)

    try:
        server_info = remote_server.server_info()
        min_required_version = server_info.min_required_weave_python_version
        trace_server_version = server_info.trace_server_version
    # TODO: Tighten this exception to only catch the specific exception
    # that is thrown by the server_info call.
    except Exception:
        # Set to a minimum version that will always pass the check
        # In the future, we may want to throw here.
        min_required_version = "0.0.0"
        trace_server_version = None
    trace_server_url = env.weave_trace_server_url()
    if not init_message.check_min_weave_version(min_required_version, trace_server_url):
        return init_weave_disabled()
    if not init_message.check_min_trace_server_version(
        trace_server_version,
        MIN_TRACE_SERVER_VERSION,
        trace_server_url,
    ):
        return init_weave_disabled()
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

    return client


def init_weave_disabled() -> weave_client.WeaveClient:
    """Initialize a dummy client that does nothing.

    This is used when the program is execuring with Weave disabled.

    Note: as currently implemented, any explicit calls to client.{X} will
    likely fail, since the user is not authenticated. The purpose of
    disabling weave is to disable _tracing_. Programs that attempt to
    make requests (eg. publishing, fetching, querying) while disabled
    will fail.
    """
    current_client = weave_client_context.get_weave_client()
    if current_client is not None:
        weave_client_context.set_weave_client_global(None)

    client = weave_client.WeaveClient(
        "DISABLED",
        "DISABLED",
        init_weave_get_server("DISABLED", should_batch=False),
        ensure_project_exists=False,
    )

    weave_client_context.set_weave_client_global(client)
    return client


def init_weave_get_server(
    api_key: str | None = None,
    should_batch: bool = True,
) -> TraceServerClientInterface:
    res: TraceServerClientInterface
    if should_use_stainless_server():
        from weave.trace_server_bindings.stainless_remote_http_trace_server import (
            StainlessRemoteHTTPTraceServer,
        )

        res = StainlessRemoteHTTPTraceServer.from_env(should_batch)
    else:
        res = RemoteHTTPTraceServer.from_env(should_batch)
    if api_key is not None:
        res.set_auth(("api", api_key))
    return res


def finish() -> None:
    current_client = weave_client_context.get_weave_client()
    if current_client is not None:
        weave_client_context.set_weave_client_global(None)

    # Unregister the import hook
    from weave.integrations.patch import unregister_import_hook

    unregister_import_hook()

    trace_sentry.global_trace_sentry.end_session()
