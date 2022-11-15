import os
import logging
from logging.config import dictConfig
import pathlib
import warnings
from pythonjsonlogger import jsonlogger

import ddtrace

ddtrace.patch(logging=True)

from flask import Flask, Blueprint
from flask import request
from flask import abort
from flask_cors import CORS, cross_origin
from flask import send_from_directory, send_file, jsonify

from weave import server
from weave import registry_mem
from weave import errors
from weave import context_state
from weave import weavejs_fixes
from weave import automation
from weave import util

from flask.logging import wsgi_errors_stream

# Ensure these are imported and registered
from weave import ops

# Load and register the ecosystem ops
# These are all treated as builtins for now.
loading_builtins_token = context_state.set_loading_built_ins()

from weave import ecosystem
from .artifacts_local import local_artifact_dir

context_state.clear_loading_built_ins(loading_builtins_token)

import sys

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


# set up logging

pid = os.getpid()
default_log_filename = pathlib.Path(f"/tmp/weave/log/{pid}.log")

default_log_format = "[%(asctime)s] %(levelname)s in %(module)s (Thread Name: %(threadName)s): %(message)s"


def is_wandb_production():
    return os.getenv("WEAVE_ENV") == "wandb_production"


def enable_stream_logging(level=logging.DEBUG, enable_datadog=False):

    log_format = (
        (
            "%(asctime)s %(levelname)s [%(name)s] [%(filename)s:%(lineno)d] "
            "[dd.trace_id=%(dd.trace_id)s dd.span_id=%(dd.span_id)s] "
            "- %(message)s"
        )
        if enable_datadog
        else default_log_format
    )

    logger = logging.getLogger("root")
    stream_handler = logging.StreamHandler(wsgi_errors_stream)
    stream_handler.setLevel(level)
    formatter = jsonlogger.JsonFormatter(log_format)
    stream_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)


static_folder = os.path.join(os.path.dirname(__file__), "frontend")
blueprint = Blueprint("weave", "weave-server", static_folder=static_folder)


def make_app(log_filename=None):
    enable_stream_logging(
        enable_datadog=os.getenv("DD_ENV"),
        level=logging.DEBUG
        if util.parse_boolean_env_var("WEAVE_SERVER_ENABLE_LOGGING")
        else logging.ERROR,
    )

    app = Flask(__name__)
    app.register_blueprint(blueprint)

    # Very important! We rely on key ordering on both sides!
    app.config["JSON_SORT_KEYS"] = False
    CORS(app, supports_credentials=True)

    return app


@blueprint.route("/__weave/ops", methods=["GET"])
def list_ops():
    if not is_wandb_production():
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


def recursively_unwrap_unions(obj):
    if isinstance(obj, list):
        return [recursively_unwrap_unions(o) for o in obj]
    if isinstance(obj, dict):
        if "_union_id" in obj and "_val" in obj:
            return recursively_unwrap_unions(obj["_val"])
        else:
            return {k: recursively_unwrap_unions(v) for k, v in obj.items()}
    return obj


@blueprint.route("/__weave/execute", methods=["POST"])
def execute():
    """Execute endpoint used by WeaveJS."""

    current_span = ddtrace.tracer.current_span()
    if current_span and (
        os.getenv("WEAVE_SERVER_DD_LOG_REQUEST_BODY_JSON")
        or request.headers.get("weave-dd-log-request-body-json")
    ):
        current_span.set_tag("json", request.json)

    if not request.json or "graphs" not in request.json:
        abort(400)
    # Simulate browser/server latency
    # import time
    # time.sleep(0.1)
    response = server.handle_request(request.json, deref=True)

    # remove unions from the response
    response = recursively_unwrap_unions(response)

    # MAJOR HACKING HERE
    # TODO: fix me
    final_response = []
    for r in response:
        # final_response.append(n)
        if isinstance(r, dict) and "_val" in r:
            r = r["_val"]
        final_response.append(weavejs_fixes.fixup_data(r))
    # print("FINAL RESPONSE", final_response)
    response = {"data": final_response}
    if current_span and (
        os.getenv("WEAVE_SERVER_DD_LOG_REQUEST_RESPONSES")
        or request.headers.get("weave-dd-log-request-response")
    ):
        current_span.set_tag("response", response)

    if request.headers.get("weave-shadow"):
        response["data"] = []

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
def send_js(path):
    # path is given relative to the FS root. check to see that path is a subdirectory of the
    # local artifacts path. if not, return 403. then if there is a cache scope function defined
    # call it to make sure we have access to the path
    abspath = "/" / pathlib.Path(
        path
    )  # add preceding slash as werkzeug strips this by default and it is reappended below in send_from_directory
    local_artifacts_path = pathlib.Path(local_artifact_dir()).absolute()
    if local_artifacts_path not in list(abspath.parents):
        abort(403)
    return send_from_directory("/", path)


@blueprint.route(
    "/__weave/automate/<string:automation_id>/add_command", methods=["POST"]
)
def automation_add_command(automation_id):
    automation.add_command(automation_id, request.json)
    return {"status": "ok"}


@blueprint.route("/__weave/automate/<string:automation_id>/commands_after/<int:after>")
def automation_commands_after(automation_id, after):
    return {"commands": automation.commands_after(automation_id, after)}


@blueprint.route(
    "/__weave/automate/<string:automation_id>/set_status", methods=["POST"]
)
def automation_set_status(automation_id):
    automation.set_status(automation_id, request.json)
    return {"status": "ok"}


@blueprint.route("/__weave/automate/<string:automation_id>/status")
def automation_status(automation_id):
    return automation.get_status(automation_id)


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


# This makes all server logs go into the notebook
app = make_app()


@app.before_first_request
def before_first_request():
    registry_mem.memory_registry.load_saved_ops()


if __name__ == "__main__":
    app.run(ssl_context="adhoc", port=9994)
