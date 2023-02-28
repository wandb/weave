import cProfile
import dataclasses
import enum
import typing
import os
import logging
import pathlib
import time
import traceback
import sys
import base64
import zlib
import urllib.parse
from flask import json
from werkzeug.exceptions import HTTPException
from werkzeug.middleware.profiler import ProfilerMiddleware

from flask import Flask, Blueprint
from flask import request
from flask import abort
from flask_cors import CORS, cross_origin
from flask import send_from_directory, send_file, jsonify

from weave import server
from weave import storage
from weave import registry_mem
from weave import errors
from weave import weavejs_fixes
from weave import util
from weave import engine_trace
from weave import environment
from weave import logs
from weave import filesystem

# PROFILE_DIR = "/tmp/weave/profile"
PROFILE_DIR = None
if PROFILE_DIR is not None:
    pathlib.Path(PROFILE_DIR).mkdir(parents=True, exist_ok=True)


tracer = engine_trace.tracer()


def custom_dd_patch():
    import wandb
    import wandb_gql
    import wandb_graphql

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


def make_app():
    logs.configure_logger()

    app = Flask(__name__)
    app.register_blueprint(blueprint)

    # Very important! We rely on key ordering on both sides!
    app.config["JSON_SORT_KEYS"] = False
    CORS(app, supports_credentials=True)

    return app


@blueprint.route("/__weave/ops", methods=["GET"])
def list_ops():
    if not environment.wandb_production():
        registry_mem.memory_registry.load_saved_ops()
    ops = registry_mem.memory_registry.list_ops()
    ret = []
    for op in ops:
        try:
            serialized_op = op.to_dict()
        except errors.WeaveSerializeError:
            continue
        if serialized_op["output_type"] != "any":
            ret.append(serialized_op)
    return {"data": ret}


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

    execute_args = {
        "request": request.json,
        "deref": True,
        "serialize_fn": storage.to_weavejs,
    }
    if not PROFILE_DIR:
        start_time = time.time()
        response = server.handle_request(**execute_args)
        elapsed = time.time() - start_time
    else:
        # Profile the request and add a link to local snakeviz to the trace.
        profile = cProfile.Profile()
        start_time = time.time()
        try:
            response = profile.runcall(server.handle_request, **execute_args)
        finally:
            elapsed = time.time() - start_time
            profile_filename = f"/tmp/weave/profile/execute.{start_time*1000:.0f}.{elapsed*1000:.0f}ms.prof"
            profile.dump_stats(profile_filename)
            root_span = tracer.current_root_span()
            if root_span:
                root_span.set_tag(
                    "profile_url",
                    "http://localhost:8080/snakeviz/"
                    + urllib.parse.quote(profile_filename),
                )
    fixed_response = [weavejs_fixes.fixup_data(r) for r in response]

    response = {"data": fixed_response}

    if request.headers.get("x-weave-include-execution-time"):
        response["execution_time"] = (elapsed) * 1000

    return response


@blueprint.route("/__weave/execute/v2", methods=["POST"])
def execute_v2():
    """Execute endpoint used by Weave Python"""
    # print('REQUEST', request, request.json)
    if not request.json or "graphs" not in request.json:
        abort(400)
    response = server.handle_request(request.json, deref=True)
    # print("RESPONSE BEFORE SERI", response)

    return {"data": response}


@blueprint.route("/__weave/file/<path:path>")
def send_local_file(path):
    # path is given relative to the FS root. check to see that path is a subdirectory of the
    # local artifacts path. if not, return 403. then if there is a cache scope function defined
    # call it to make sure we have access to the path
    abspath = "/" / pathlib.Path(
        path
    )  # add preceding slash as werkzeug strips this by default and it is reappended below in send_from_directory
    local_artifacts_path = pathlib.Path(filesystem.get_filesystem_dir()).absolute()
    if local_artifacts_path not in list(abspath.parents):
        abort(403)
    return send_from_directory("/", path)


@blueprint.route("/__frontend", defaults={"path": None})
@blueprint.route("/__frontend/<path:path>")
def frontend(path):
    """Serve the frontend with a simple fileserver over HTTP."""
    full_path = pathlib.Path(blueprint.static_folder) / path
    if path and full_path.exists():
        return send_from_directory(blueprint.static_folder, path)
    else:
        return send_from_directory(blueprint.static_folder, "index.html")


@blueprint.route("/__weave/hello")
def hello():
    return "hello"


DEBUG_MEM = False
if not environment.wandb_production() and DEBUG_MEM:
    # To use, hit /objgraph_getnewids to set a baseline, then do some requests.
    # Then hit /pdb to drop the server into pdb and do
    # import objgraph
    # obj_ids = objgraph.get_new_ids()
    # This will contain all the ids of objects that have been created since
    # the last call to objgraph.get_new_ids()
    # Then you can inspect objects like:
    # obj_id = obj_ids['TypedDict'][0]
    # obj = objgraph.at(obj_id)
    # objgraph.show_backrefs([obj], max_depth=15)
    #
    # Other useful objgraph commands:
    # objgraph.show_most_common_types(limit=20)
    # obj = objgraph.by_type('TypedDict')[100]

    import gc
    import objgraph

    @blueprint.route("/pdb")
    def pdb():
        breakpoint()
        return "ok"

    @blueprint.route("/objgraph_showgrowth")
    def objgraph_showgrowth():
        gc.collect()
        objgraph.show_growth()
        return "see logs"

    @blueprint.route("/objgraph_getnewids")
    def objgraph_getnewids():
        gc.collect()
        objgraph.get_new_ids()
        return "see logs"


# This makes all server logs go into the notebook
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


@app.before_first_request
def before_first_request():
    if not util.parse_boolean_env_var("WEAVE_SERVER_DISABLE_ECOSYSTEM"):
        try:
            from weave.ecosystem import all
        except ImportError:
            logging.warning(
                'Failed to import "weave.ecosystem". Weave ecosystem features will be disabled. '
                'To fix this, install ecosystem dependencies with "pip install weave[ecosystem]". '
                "To disable this message, set WEAVE_SERVER_DISABLE_ECOSYSTEM=1."
            )


if __name__ == "__main__":
    app.run(ssl_context="adhoc", port=9994)
