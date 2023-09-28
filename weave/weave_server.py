import cProfile
import os
import logging
import pathlib
import time
import traceback
import sys
import base64
import typing
import zlib
import urllib.parse
import requests
from flask import json
from werkzeug.exceptions import HTTPException

from flask import Flask, Blueprint, Response
from flask import request
from flask import abort
from flask_cors import CORS
from flask import send_from_directory, redirect
import wandb

from weave import context_state, graph, server, value_or_error
from weave import storage
from weave import registry_mem
from weave import errors
from weave import weavejs_fixes
from weave import util
from weave import engine_trace
from weave import environment
from weave import logs
from weave import filesystem
from weave.server_error_handling import client_safe_http_exceptions_as_werkzeug
from weave import storage
from weave import wandb_api
from weave.language_features.tagging import tag_store

logger = logging.getLogger(__name__)

WEAVE_CLIENT_CACHE_KEY_HEADER = "x-weave-client-cache-key"

# PROFILE_DIR = "/tmp/weave/profile"
PROFILE_DIR = None
if PROFILE_DIR is not None:
    pathlib.Path(PROFILE_DIR).mkdir(parents=True, exist_ok=True)

ERROR_STR_LIMIT = 10000

tracer = engine_trace.tracer()


def custom_dd_patch():
    import wandb_gql  # type: ignore[import]
    import wandb_graphql  # type: ignore[import]

    orig_execute = wandb_gql.Client.execute

    def execute(self, document, *args, **kwargs):
        with tracer.trace(
            "wandb_gql.Client.execute",
        ) as span:
            span.set_tag("document", wandb_graphql.print_ast(document))
            span.set_tag("variable_values", kwargs.get("variable_values", {}))
            return orig_execute(self, document, *args, **kwargs)

    wandb_gql.Client.execute = execute


if engine_trace.datadog_is_enabled():
    # Don't import this if you don't have an Agent! You'll get weird
    # crashes
    import ddtrace

    ddtrace.patch_all(logging=True)
    custom_dd_patch()


# Ensure these are imported and registered
from weave import ops


# NOTE: Fixes flask dev server's auto-reload capability, by forcing it to use
# stat mode instead of watchdog mode. It turns out that "import wandb" breaks
# users of watchdog somehow. We'll need to fix that in wandb.
# A wandb fix should go out in 0.13.5.
# TODO: remove this hack when wandb 0.13.5 is released.
if os.environ.get("FLASK_DEBUG"):
    print(
        "!!! Weave server removing watchdog from sys.path for development mode. This could break other libraries"
    )
    sys.modules["watchdog.observers"] = None  # type: ignore


static_folder = os.path.join(os.path.dirname(__file__), "frontend")
blueprint = Blueprint("weave", "weave-server", static_folder=static_folder)


def import_ecosystem():
    # Attempt to import MVP ecosystem modules
    try:
        from weave.ecosystem import langchain, replicate
    except ImportError:
        pass

    if not util.parse_boolean_env_var("WEAVE_SERVER_DISABLE_ECOSYSTEM"):
        try:
            from weave.ecosystem import all
        except (ImportError, OSError, wandb.Error):
            pass


def log_system_info():
    WEAVE_SERVER_URL = os.environ.get("WEAVE_SERVER_URL")
    WANDB_BASE_URL = os.environ.get("WANDB_BASE_URL", "http://api.wandb.ai")
    WEAVE_LOCAL_ARTIFACT_DIR = os.environ.get("WEAVE_LOCAL_ARTIFACT_DIR")
    dot_netrc_exists = os.path.exists(os.path.expanduser("~/.netrc"))
    underscore_netrc_exists = os.path.exists(os.path.expanduser("~/_netrc"))
    WANDB_API_KEY = "REDACTED" if os.environ.get("WANDB_API_KEY") else None
    WEAVE_WANDB_COOKIE = "REDACTED" if os.environ.get("WEAVE_WANDB_COOKIE") else None

    logger.info("Network Config:")
    logger.info(f"  WEAVE_SERVER_URL    = {WEAVE_SERVER_URL}")
    logger.info(f"  WANDB_BASE_URL      = {WANDB_BASE_URL}")

    logger.info("Cache Config:")
    logger.info(f"  WEAVE_LOCAL_ARTIFACT_DIR  = {WEAVE_LOCAL_ARTIFACT_DIR}")

    logger.info("Auth Config:")
    logger.info(f"  ~/.netrc exists     = {dot_netrc_exists}")
    logger.info(f"  ~/_netrc exists     = {underscore_netrc_exists}")
    logger.info(f"  WANDB_API_KEY       = {WANDB_API_KEY}")
    logger.info(f"  WEAVE_WANDB_COOKIE  = {WEAVE_WANDB_COOKIE}")


def make_app():
    logs.configure_logger()
    import_ecosystem()

    logger.info("Starting weave server")
    log_system_info()

    app = Flask(__name__)
    app.register_blueprint(blueprint)
    # Very important! We rely on key ordering on both sides!
    # Flask < 2.2 doesn't have app.json
    if hasattr(app, "json"):
        app.json.sort_keys = False
    else:
        app.config["JSON_SORT_KEYS"] = False

    CORS(app, supports_credentials=True)

    return app


class OpsCache(typing.TypedDict):
    updated_at: float
    ops_data: typing.Optional[dict]


ops_cache: typing.Optional[OpsCache] = None


@blueprint.route("/__weave/ops", methods=["GET"])
def list_ops():
    global ops_cache
    with wandb_api.from_environment():
        # TODO: this is super slow.
        if not environment.wandb_production():
            registry_mem.memory_registry.load_saved_ops()
            pass
        if (
            ops_cache is None
            or ops_cache["updated_at"] < registry_mem.memory_registry.updated_at()
        ):
            ops = registry_mem.memory_registry.list_ops()
            ret = []
            for op in ops:
                try:
                    serialized_op = op.to_dict()
                except errors.WeaveSerializeError:
                    continue
                ret.append(serialized_op)
            ops_cache = {
                "updated_at": registry_mem.memory_registry.updated_at(),
                "data": ret,
            }
    return ops_cache


class ErrorDetailsDict(typing.TypedDict):
    message: str
    error_type: str
    traceback: list[str]
    # sentry_id: typing.Union[str, None]


class ResponseDict(typing.TypedDict):
    data: list[typing.Any]
    errors: list[ErrorDetailsDict]
    node_to_error: dict[int, int]


def _exception_to_error_details(
    e: Exception, sentry_id: typing.Union[str, None]
) -> ErrorDetailsDict:
    return {
        "error_type": type(e).__name__,
        "message": str(e),
        "traceback": traceback.format_tb(e.__traceback__),
        # "sentry_id": sentry_id,
    }


def _value_or_errors_to_response(
    vore: value_or_error.ValueOrErrors,
) -> ResponseDict:
    error_lookup: dict[Exception, typing.Tuple[int, typing.Union[str, None]]] = {}
    node_errors: dict[int, int] = {}
    data: list[typing.Any] = []
    for val, error in vore.iter_items():
        if error != None:
            error = typing.cast(Exception, error)
            data.append(None)
            if error in error_lookup:
                error_ndx = error_lookup[error][0]
            else:
                sentry_id = util.capture_exception_with_sentry_if_available(error, ())
                error_ndx = len(error_lookup)
                error_lookup[error] = (error_ndx, sentry_id)
            node_errors[len(data) - 1] = error_ndx
        else:
            data.append(val)
    return {
        "data": data,
        "errors": [
            _exception_to_error_details(k, e_sentry_id)
            for k, (e_ndx, e_sentry_id) in error_lookup.items()
        ],
        "node_to_error": node_errors,
    }


def _log_errors(
    processed_response: ResponseDict, nodes: value_or_error.ValueOrErrors[graph.Node]
):
    errors: list[dict] = []

    for error in processed_response["errors"]:
        errors.append(
            {
                "message": error["message"],
                "error_type": error["error_type"],
                "traceback": error["traceback"],
                "error_tag": "node_execution_error",
                "node_strs": [],
                # "sentry_id": error["sentry_id"],
            }
        )

    for node_ndx, error_ndx in processed_response["node_to_error"].items():
        try:
            node_str = graph.node_expr_str(graph.map_const_nodes_to_x(nodes[node_ndx]))
            errors[error_ndx]["node_strs"].append(node_str)
        except Exception:
            pass

    for error_dict in errors:
        # This should be logged to DD, but 1 log per error
        # class, not 1 log per error.
        logging.error(error_dict)


def _get_client_cache_key_from_request(request):
    # Uncomment to set default to 15 second cache duration
    client_cache_key = None  # str(int(time.time() // 15))
    if WEAVE_CLIENT_CACHE_KEY_HEADER in request.headers:
        client_cache_key = request.headers[WEAVE_CLIENT_CACHE_KEY_HEADER]
    return client_cache_key


@blueprint.route("/__weave/execute", methods=["POST"])
def execute():
    """Execute endpoint used by WeaveJS."""
    with tracer.trace("read_request"):
        req_bytes = request.data
    req_compressed = zlib.compress(req_bytes)
    req_b64 = base64.b64encode(req_compressed).decode("ascii")
    logging.info(
        "Execute request (zlib): %s",
        req_b64,
    )

    if not request.json:
        abort(400, "Request body must be JSON.")
    if "graphs" not in request.json:
        abort(400, "Request body must contain a 'graphs' key.")

    # Simulate browser/server latency
    # import time
    # time.sleep(0.1)

    # use a single memartifact to serialize the entire response.
    # fixes https://weights-biases.sentry.io/issues/4022569419

    execute_args = {
        "request": request.json,
        "deref": True,
        "serialize_fn": storage.make_js_serializer(),
    }
    root_span = tracer.current_root_span()
    tag_store.record_current_tag_store_size()

    client_cache_key = _get_client_cache_key_from_request(request)

    if not PROFILE_DIR:
        start_time = time.time()
        with client_safe_http_exceptions_as_werkzeug():
            with context_state.set_client_cache_key(client_cache_key):
                response = server.handle_request(**execute_args)
        elapsed = time.time() - start_time
    else:
        # Profile the request and add a link to local snakeviz to the trace.
        profile = cProfile.Profile()
        start_time = time.time()
        try:
            with client_safe_http_exceptions_as_werkzeug():
                with context_state.set_client_cache_key(client_cache_key):
                    response = profile.runcall(server.handle_request, **execute_args)
        finally:
            elapsed = time.time() - start_time
            profile_filename = f"/tmp/weave/profile/execute.{start_time*1000:.0f}.{elapsed*1000:.0f}ms.prof"
            profile.dump_stats(profile_filename)
            if root_span:
                root_span.set_tag(
                    "profile_url",
                    "http://localhost:8080/snakeviz/"
                    + urllib.parse.quote(profile_filename),
                )
    if root_span is not None:
        root_span.set_tag("request_size", len(req_bytes))
    fixed_response = response.results.safe_map(weavejs_fixes.fixup_data)

    response_payload = _value_or_errors_to_response(fixed_response)

    if root_span is not None:
        root_span.set_metric("node_count", len(response_payload["data"]))
        root_span.set_metric("error_count", len(response_payload["node_to_error"]))

    _log_errors(response_payload, response.nodes)

    if request.headers.get("x-weave-include-execution-time"):
        response_payload["execution_time"] = (elapsed) * 1000

    return response_payload


@blueprint.route("/__weave/execute/v2", methods=["POST"])
def execute_v2():
    """Execute endpoint used by Weave Python"""
    # print('REQUEST', request, request.json)
    if not request.json or "graphs" not in request.json:
        abort(400)
    response = server.handle_request(request.json, deref=True)
    # print("RESPONSE BEFORE SERI", response)

    return {"data": response.results.unwrap()}


@blueprint.route("/__weave/file/<path:path>")
def send_local_file(path):
    # path is given relative to the FS root. check to see that path is a subdirectory of the
    # local artifacts path. if not, return 403. then if there is a cache scope function defined
    # call it to make sure we have access to the path
    abspath = "/" / pathlib.Path(
        path
    )  # add preceding slash as werkzeug strips this by default and it is reappended below in send_from_directory
    try:
        local_artifacts_path = pathlib.Path(filesystem.get_filesystem_dir()).absolute()
    except errors.WeaveAccessDeniedError:
        abort(403)
    if local_artifacts_path not in list(abspath.parents):
        abort(403)
    return send_from_directory("/", path)


def frontend_env():
    """If you add vars here, make sure to define their types in weave-js/src/config.ts"""
    return {
        "PREFIX": environment.weave_link_prefix(),
        "ANALYTICS_DISABLED": environment.analytics_disabled(),
        "ONPREM": environment.weave_onprem(),
        "WEAVE_BACKEND_HOST": environment.weave_backend_host(),
        "WANDB_BASE_URL": environment.wandb_base_url(),
    }


@blueprint.route("/__frontend", defaults={"path": None})
@blueprint.route("/__frontend/<path:path>")
def frontend(path):
    """Serve the frontend with a simple fileserver over HTTP."""
    # We serve up a dynamic env.js file before all other js.
    if path is not None and path.endswith("env.js"):
        js = f"window.WEAVE_CONFIG = {json.dumps(frontend_env())}"
        return Response(js, mimetype="application/javascript")
    full_path = pathlib.Path(blueprint.static_folder) / path
    # prevent path traversal
    if not full_path.resolve().is_relative_to(blueprint.static_folder):
        return abort(403)
    if path and full_path.exists():
        return send_from_directory(blueprint.static_folder, path)
    else:
        return send_from_directory(blueprint.static_folder, "index.html")


@blueprint.route("/", defaults={"path": None})
@blueprint.route("/<path:path>")
def root_frontend(path):
    if request.args.get("unsetBetaVersion") is not None:
        resp = redirect_without_query_param("unsetBetaVersion")
        resp.set_cookie("betaVersion", "", max_age=0)
        return resp

    new_beta_version = request.args.get("betaVersion")
    if new_beta_version is not None:
        resp = redirect_without_query_param("betaVersion")
        resp.set_cookie("betaVersion", new_beta_version)
        return resp

    # To support server cases where we're mounted under an existing path, i.e.
    # /wandb/weave, then index.html will load something like /wandb/weave/.../env.js
    if path is not None:
        path = path.split("/")[-1]
    if path == "env.js":
        js = f"window.WEAVE_CONFIG = {json.dumps(frontend_env())}"
        return Response(js, mimetype="application/javascript")

    beta_version = request.cookies.get("betaVersion")
    if beta_version is not None:
        beta_version = beta_version[:9]
        content = requests.get(
            f"https://cdn.wandb.ai/weave/{beta_version}/index.html",
            stream=True,
        ).content
        return Response(content, mimetype="text/html")

    return send_from_directory(blueprint.static_folder, "index.html")


def redirect_without_query_param(param: str):
    qs_pairs = []
    for k, v in request.args.items():
        if k != param:
            qs_pairs.append(f"{k}={v}")
    qs = "&".join(qs_pairs)
    resp = redirect(f"{request.path}?{qs}")
    return resp


@blueprint.route("/__weave/hello")
def hello():
    return "hello"


@blueprint.route("/__weave/wb_viewer", methods=["POST"])
def wb_viewer():
    wandb_api.init()
    current_context = wandb_api.get_wandb_api_context()
    if not current_context:
        with wandb_api.from_environment():
            current_context = wandb_api.get_wandb_api_context()
    authenticated = current_context is not None
    user_id = None if current_context is None else current_context.user_id
    return {"authenticated": authenticated, "user_id": user_id}


app = make_app()

if os.getenv("WEAVE_SERVER_DEBUG"):

    @app.errorhandler(HTTPException)
    def handle_exception(e):
        """Return JSON instead of HTML for HTTP errors."""
        # start with the correct headers and status code from the error
        response = e.get_response()
        # replace the body with JSON
        response.data = json.dumps(
            {
                "code": e.code,
                "name": e.name,
                "description": e.description,
                "exc_info": traceback.format_exc(),
            }
        )
        response.content_type = "application/json"
        return response


if __name__ == "__main__":
    app.run(port=9994)
