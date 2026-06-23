from urllib.parse import quote

from weave.compat import wandb
from weave.trace import env

BROWSE3_PATH = "browse3"
WEAVE_SLUG = "weave"

# OTel GenAI traces ingestion path on the weave trace server. Appended to
# ``weave_trace_server_url()`` to form the OTLP HTTP exporter endpoint.
_OTEL_GENAI_TRACES_PATH = "/agents/otel/v1/traces"


def otel_traces_endpoint(base_url: str | None = None) -> str:
    """Return the full OTLP HTTP endpoint URL for Weave GenAI trace ingestion.

    External callers (e.g. boot-time probes that want to verify the
    ingest endpoint is reachable before relying on the BatchSpanProcessor
    to silently drop exports) should call this rather than constructing
    the URL by hand. The path is owned by the SDK and may move.

    Args:
        base_url: Trace server base URL. Defaults to
            ``weave_trace_server_url()``.
    """
    server_url = (base_url or env.weave_trace_server_url()).rstrip("/")
    return f"{server_url}{_OTEL_GENAI_TRACES_PATH}"


def remote_project_root_url(entity_name: str, project_name: str) -> str:
    return f"{wandb.app_url(env.wandb_base_url())}/{entity_name}/{quote(project_name)}"


def project_weave_root_url(entity_name: str, project_name: str) -> str:
    return f"{remote_project_root_url(entity_name, project_name)}/{WEAVE_SLUG}"


def op_version_path(
    entity_name: str, project_name: str, op_name: str, op_version: str
) -> str:
    return f"{project_weave_root_url(entity_name, project_name)}/ops/{op_name}/versions/{op_version}"


def object_version_path(
    entity_name: str, project_name: str, object_name: str, obj_version: str
) -> str:
    return f"{project_weave_root_url(entity_name, project_name)}/objects/{quote(object_name)}/versions/{obj_version}"


def leaderboard_path(entity_name: str, project_name: str, object_name: str) -> str:
    return f"{project_weave_root_url(entity_name, project_name)}/leaderboards/{quote(object_name)}"


def redirect_call(entity_name: str, project_name: str, call_id: str) -> str:
    return f"{remote_project_root_url(entity_name, project_name)}/r/call/{call_id}"


def agent_conversation_path(
    entity_name: str, project_name: str, conversation_id: str
) -> str:
    return f"{project_weave_root_url(entity_name, project_name)}/agents/conversations/{quote(conversation_id)}"
