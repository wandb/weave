import os
import logging
from logging.config import dictConfig
from logging.handlers import WatchedFileHandler
import pathlib
import warnings
import json_log_formatter

import traceback
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

from flask.logging import wsgi_errors_stream

# Ensure these are imported and registered
from weave import ops

# Load and register the ecosystem ops
# These are all treated as builtins for now.
loading_builtins_token = context_state.set_loading_built_ins()

from weave import ecosystem
from .artifacts_local import local_artifact_dir

context_state.clear_loading_built_ins(loading_builtins_token)


# set up logging

pid = os.getpid()
default_log_filename = pathlib.Path(f"/tmp/weave/log/{pid}.log")
log_format = "[%(asctime)s] %(levelname)s in %(module)s (Thread Name: %(threadName)s): %(message)s"


def enable_datadog_logging():
    log_format = (
        "%(asctime)s %(levelname)s [%(name)s] [%(filename)s:%(lineno)d] "
        "[dd.service=%(dd.service)s dd.env=%(dd.env)s dd.version=%(dd.version)s dd.trace_id=%(dd.trace_id)s dd.span_id=%(dd.span_id)s] "
        "- %(message)s"
    )
    formatter = json_log_formatter.JSONFormatter(log_format)
    json_handler = logging.FileHandler(filename="/tmp/weave/log/weave-server.log")
    json_handler.setFormatter(formatter)
    logger = logging.getLogger("root")
    logger.addHandler(json_handler)


def enable_stream_logging(level=logging.DEBUG):
    logger = logging.getLogger("root")
    stream_handler = logging.StreamHandler(wsgi_errors_stream)
    stream_handler.setLevel(level)
    formatter = logging.Formatter(log_format)
    stream_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)


static_folder = os.path.join(os.path.dirname(__file__), "frontend")
blueprint = Blueprint("weave", "weave-server", static_folder=static_folder)


def make_app(log_filename=None):
    fs_logging_enabled = True
    log_file = log_filename or default_log_filename

    try:
        log_file.parent.mkdir(exist_ok=True, parents=True)
        log_file.touch(exist_ok=True)
    except OSError:
        warnings.warn(
            f"weave: Unable to touch logfile at '{log_file}'. Filesystem logging will be disabled for "
            f"the remainder of this session. To enable filesystem logging, ensure the path is writable "
            f"and restart the server."
        )
        fs_logging_enabled = False

    logging_config = {
        "version": 1,
        "formatters": {
            "default": {
                "format": log_format,
            }
        },
        "handlers": {
            "wsgi_file": {
                "class": "logging.handlers.WatchedFileHandler",
                "filename": log_file,
                "formatter": "default",
            },
        },
        "root": {
            "level": "DEBUG",
            "handlers": ["wsgi_file"] if fs_logging_enabled else [],
        },
    }

    dictConfig(logging_config)

    if os.getenv("WEAVE_SERVER_ENABLE_LOGGING"):
        enable_stream_logging()
    else:
        # ensure that errors / exceptions go to stderr
        enable_stream_logging(level=logging.ERROR)

    if os.getenv("DD_ENV"):
        enable_datadog_logging()

    app = Flask(__name__)
    app.register_blueprint(blueprint)

    # Very important! We rely on key ordering on both sides!
    app.config["JSON_SORT_KEYS"] = False
    CORS(app, supports_credentials=True)

    return app


@blueprint.route("/__weave/ops", methods=["GET"])
def list_ops():
    ops = registry_mem.memory_registry.list_ops()
    ret = []
    for op in ops:
        try:
            ret.append(op.to_dict())
        except errors.WeaveSerializeError:
            pass
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
            final_response.append(r["_val"])
        else:
            final_response.append(r)
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


if __name__ == "__main__":
    app.run(ssl_context="adhoc", port=9994)
