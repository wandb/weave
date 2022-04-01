import os
import logging
import pathlib
import typing
import warnings

from flask import Flask
from flask import request
from flask import abort
from flask_cors import CORS
from flask import send_from_directory
from flask.logging import default_handler, wsgi_errors_stream

from weave import server
from weave import registry_mem

# Ensure we register the openai ops so we can tell the
# app about them with list_ops
from weave.ecosystem import openai
from weave.ecosystem import async_demo

# set up logging

wz_logger = logging.getLogger("werkzeug")
wz_logger.removeHandler(default_handler)


def make_app(
    log_filename: typing.Union[str, pathlib.Path] = None, stream_enabled: bool = False
) -> Flask:
    pid = os.getpid()
    log_file = log_filename or pathlib.Path(f"./.weave/log/{pid}.log")
    fs_logging_enabled = True

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

    app = Flask(__name__, static_folder="frontend")
    app.logger.removeHandler(default_handler)

    formatter = logging.Formatter(
        "[%(asctime)s] %(levelname)s in %(module)s (Thread %(thread)s): %(message)s"
    )

    if fs_logging_enabled:
        handler = logging.FileHandler(log_file)
        handler.setLevel(logging.INFO)
        handler.setFormatter(formatter)
        app.logger.addHandler(handler)
        wz_logger.addHandler(handler)

    if stream_enabled:
        handler = logging.StreamHandler(wsgi_errors_stream)
        handler.setLevel(logging.WARNING)
        handler.setFormatter(formatter)
        app.logger.addHandler(handler)
        wz_logger.addHandler(handler)

    @app.route("/__weave/ops", methods=["GET"])
    def list_ops():
        ops = registry_mem.memory_registry.list_ops()
        ret = []
        for op in ops:
            if callable(op.output_type):
                # print("NOT registering op: ", op.name)
                # skip these for now. add back in later.
                continue
            # print("Registering op: ", op.name)

            input_types = {key: op.input_type[key].to_dict() for key in op.input_type}

            output_type = op.output_type.to_dict()

            serialized = {
                "name": op.name,
                "input_types": input_types,
                "output_type": output_type,
            }
            if op.render_info is not None:
                serialized["render_info"] = op.render_info
            ret.append(serialized)
        return {"data": ret}

    @app.route("/__weave/execute", methods=["POST"])
    def execute():
        # print('REQUEST', request, request.json)
        if not request.json or "graphs" not in request.json:
            abort(400)
        response = server.handle_request(request.json, deref=True)

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
        return {"data": final_response}

    @app.route("/__weave/execute/v2", methods=["POST"])
    def execute_v2():
        # print('REQUEST', request, request.json)
        if not request.json or "graphs" not in request.json:
            abort(400)
        response = server.handle_request(request.json)
        # print("RESPONSE BEFORE SERI", response)

        return {"data": response}

    @app.route("/__weave/file/<path:path>")
    def send_js(path):
        return send_from_directory("/", path)

    @app.route("/__frontend", defaults={"path": None})
    @app.route("/__frontend/<path:path>")
    def frontend(path):
        """Serve the frontend with a simple fileserver over HTTP."""
        full_path = pathlib.Path(app.static_folder) / path
        if path and full_path.exists():
            return send_from_directory(app.static_folder, path)
        else:
            return send_from_directory(app.static_folder, "index.html")

    @app.route("/__weave/hello")
    def hello():
        return "hello"

    CORS(app)
    return app


if __name__ == "__main__":
    app = make_app()
    app.run(ssl_context="adhoc", port=9994)
