from __future__ import annotations

import base64
import logging
import os
from typing import TYPE_CHECKING, Any

from weave.compat import wandb
from weave.integrations.patch import (
    implicit_patch,
    register_import_hook,
    unregister_import_hook,
)
from weave.telemetry import trace_sentry
from weave.trace import env, init_message, weave_client
from weave.trace.context import weave_client_context
from weave.trace.settings import (
    should_redact_pii,
    should_use_stainless_server,
    use_server_cache,
)
from weave.trace.urls import otel_traces_endpoint
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
from weave.wandb_interface.context import get_wandb_api_context

if TYPE_CHECKING:
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
        OTLPSpanExporter,
    )
    from opentelemetry.sdk.trace import TracerProvider

    from weave.trace.op import PostprocessInputsFunc, PostprocessOutputFunc
    from weave.trace_server.service_interface import ServerInfoRes

logger = logging.getLogger(__name__)

# The conversation/agent OTel provider is set once (OTel's global provider is
# set-once and its Resource is immutable). A later weave.init() to a different
# project reroutes by rewriting the exporter's headers instead of rebuilding,
# so agent spans (and their creds) follow the active project.
_conversation_tracer_provider: TracerProvider | None = None
_conversation_span_exporter: OTLPSpanExporter | None = None

# Bound the pre-reroute flush so switching projects can't block weave.init() on a
# stalled exporter; spans that miss the window export under the new project.
_CONVERSATION_REROUTE_FLUSH_TIMEOUT_MS = 5000


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
                    "Could not determine a W&B entity for this project. Fix with one of:\n"
                    "  1. Pass the project as 'entity/project' to weave.init(...)\n"
                    "  2. Set the WANDB_ENTITY environment variable\n"
                    "  3. Set a default entity on your W&B account and re-run "
                    "weave.init(...) to re-authenticate"
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


def _get_server_info(server: TraceServerClientInterface) -> ServerInfoRes | None:
    """Fetch server_info or return None if the server is unavailable."""
    try:
        return server.server_info()
    except Exception:
        logger.warning(
            "Unexpected error when checking if Weave is available on the server. "
            "Please contact support.",
            exc_info=True,
        )
        return None


def _setup_conversation_tracing(entity: str, project: str, api_key: str | None) -> None:
    """Configure OTel TracerProvider for the Conversation SDK using weave credentials.

    Called automatically by init_weave() once version checks have passed.
    Sets the global OTel TracerProvider so that ``trace.get_tracer("weave.conversation")``
    returns a real tracer.

    On a later weave.init() to a different project, reroutes the existing
    exporter to the new project instead of rebuilding (see the module-level
    provider globals). No-ops if the trace server URL is not configured. Logs
    a warning and returns early if opentelemetry is unavailable. Other errors
    propagate so misconfiguration is visible to the user.
    """
    global _conversation_tracer_provider, _conversation_span_exporter  # noqa: PLW0603
    try:
        from opentelemetry import trace
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
            OTLPSpanExporter,
        )
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor

        from weave.evaluation.otel_eval_linker import EvalLinkSpanProcessor
    except ImportError as e:
        logger.warning(
            "Conversation SDK tracing skipped: opentelemetry not available (%s)", e
        )
        return

    trace_server_url = env.weave_trace_server_url()
    if not trace_server_url:
        return

    project_id = f"{entity}/{project}"
    headers = _conversation_headers(project_id, api_key)

    # Re-init while we own the global provider: it's set-once with an immutable
    # Resource, so reroute the live exporter's headers instead of rebuilding.
    existing_provider = _conversation_tracer_provider
    existing_exporter = _conversation_span_exporter
    if (
        existing_provider is not None
        and existing_exporter is not None
        and trace.get_tracer_provider() is existing_provider
    ):
        # TODO: mutating the exporter's private requests.Session couples us to
        # http-proto internals; a delegating SpanExporter would drop the poke.
        current = existing_exporter._session.headers
        if current.get("project_id") == headers["project_id"] and current.get(
            "Authorization"
        ) == headers.get("Authorization"):
            return
        # Bounded flush of spans queued under the old project before re-heading,
        # so in-flight spans export under the old project_id (binds at export).
        if not existing_provider.force_flush(_CONVERSATION_REROUTE_FLUSH_TIMEOUT_MS):
            logger.warning(
                "Conversation tracing: flush timed out (%dms) before project reroute; "
                "some queued spans may export under the new project",
                _CONVERSATION_REROUTE_FLUSH_TIMEOUT_MS,
            )
        current["project_id"] = headers["project_id"]
        if "Authorization" in headers:
            current["Authorization"] = headers["Authorization"]
        else:
            current.pop("Authorization", None)
        return

    # A provider we didn't install is active (e.g. the user configured their
    # own before weave.init()); leave it untouched.
    if isinstance(trace.get_tracer_provider(), TracerProvider):
        return

    endpoint = otel_traces_endpoint(trace_server_url)
    resource = Resource.create({"service.name": "weave-conversation-sdk"})
    exporter = OTLPSpanExporter(endpoint=endpoint, headers=headers)
    # Honor WEAVE_INSECURE_DISABLE_SSL for the OTel exporter too, so
    # dev environments with self-signed certs can export spans.
    # OTLPSpanExporter passes _certificate_file to requests.post(verify=...),
    # but its constructor uses `certificate_file or <env_default>` which
    # treats False as falsy, so we set it directly after construction.
    if not env.ssl_verify():
        exporter._certificate_file = False
    provider = TracerProvider(resource=resource)
    provider.add_span_processor(BatchSpanProcessor(exporter))
    # Auto-link GenAI OTel spans to eval predictions and inject eval
    # metadata (call ID, project, evaluation name) onto spans for
    # deep-linking in the agent traces UI.
    provider.add_span_processor(EvalLinkSpanProcessor())
    trace.set_tracer_provider(provider)
    # No-op if another provider won the set-once race after our check above;
    # only record ownership if ours took, else we leak/mis-route on re-init.
    if trace.get_tracer_provider() is not provider:
        provider.shutdown()
        return
    _conversation_tracer_provider = provider
    _conversation_span_exporter = exporter


def _conversation_headers(project_id: str, api_key: str | None) -> dict[str, str]:
    """Export headers routing agent spans: project via project_id, creds via Basic auth."""
    # Auth mirrors the rest of weave (BasicAuth base64("api:<key>")); one source
    # of truth so setup and reroute never diverge into stale creds.
    headers: dict[str, str] = {"project_id": project_id}
    if api_key:
        token = base64.b64encode(f"api:{api_key}".encode()).decode()
        headers["Authorization"] = f"Basic {token}"
    return headers


def init_weave(
    project_name: str,
    ensure_project_exists: bool = True,
    *,
    postprocess_inputs: PostprocessInputsFunc | None = None,
    postprocess_output: PostprocessOutputFunc | None = None,
    attributes: dict[str, Any] | None = None,
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

    api_key = get_wandb_api_context()
    if api_key is None:
        url = wandb.app_url(env.wandb_base_url())
        logger.info("Please login to Weights & Biases (%s) to continue...", url)
        wandb.login(anonymous="never", force=True, referrer="weave")  # type: ignore
        api_key = get_wandb_api_context()

    # Resolve entity name after authentication is ensured
    entity_name, project_name = get_entity_project_from_project_name(project_name)
    wb_run_context = get_global_wb_run_context()
    if wb_run_context:
        wandb_run_id = f"{entity_name}/{project_name}/{wb_run_context.run_id}"
        check_wandb_run_matches(wandb_run_id, entity_name, project_name)

    remote_server = init_weave_get_server(api_key)
    server_info = _get_server_info(remote_server)
    if server_info is None:
        raise RuntimeError(
            "Weave is not available on the server.  Please contact support."
        )
    server: TraceServerClientInterface = remote_server
    if use_server_cache():
        server = CachingMiddlewareTraceServer.from_env(server)

    client = weave_client.WeaveClient(
        entity_name,
        project_name,
        server,
        ensure_project_exists,
        postprocess_inputs=postprocess_inputs,
        postprocess_output=postprocess_output,
        attributes=attributes,
        api_key=api_key,
    )

    # If the project name was formatted by init, update the project name
    project_name = client.project

    weave_client_context.set_weave_client_global(client)

    # Implicit patching:
    # 1. Check sys.modules and automatically patch any already-imported integrations
    # 2. Register import hook to patch integrations imported after weave.init()
    implicit_patch()
    register_import_hook()

    username = get_username()

    # This is a temporary event to track the number of users who have enabled PII redaction.
    if should_redact_pii():
        from weave.utils.pii_redaction import track_pii_redaction_enabled

        track_pii_redaction_enabled(username or "unknown", entity_name, project_name)

    min_required_version = server_info.min_required_weave_python_version
    trace_server_version = server_info.trace_server_version
    trace_server_url = env.weave_trace_server_url()
    if not init_message.check_min_weave_version(min_required_version, trace_server_url):
        return init_weave_disabled()
    if not init_message.check_min_trace_server_version(
        trace_server_version,
        MIN_TRACE_SERVER_VERSION,
        trace_server_url,
    ):
        return init_weave_disabled()

    # Configure Conversation SDK OTel tracing using the same server credentials.
    # Placed after the version checks so a disabled init never installs a
    # global TracerProvider that would keep exporting spans to an
    # incompatible server.
    _setup_conversation_tracing(entity_name, project_name, api_key)

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


def init_weave_disabled(
    *,
    postprocess_inputs: PostprocessInputsFunc | None = None,
    postprocess_output: PostprocessOutputFunc | None = None,
    attributes: dict[str, Any] | None = None,
) -> weave_client.WeaveClient:
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
        postprocess_inputs=postprocess_inputs,
        postprocess_output=postprocess_output,
        attributes=attributes,
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
    unregister_import_hook()

    trace_sentry.global_trace_sentry.end_session()
