import logging
import pathlib

from flask import Flask
from flask import request
from flask import abort
from flask_cors import CORS
from flask import send_from_directory

from weave import server
from weave import registry_mem
from weave import op_args
from weave import errors

# Ensure we register the openai ops so we can tell the
# app about them with list_ops
from weave.ecosystem import openai
from weave.ecosystem import async_demo

app = Flask(__name__, static_folder="frontend")
log = logging.getLogger("werkzeug")
log.setLevel(logging.ERROR)
CORS(app)


@app.route("/__weave/ops", methods=["GET"])
def list_ops():
    ops = registry_mem.memory_registry.list_ops()
    ret = []
    for op in ops:
        try:
            ret.append(op.to_dict())
        except errors.WeaveSerializeError:
            pass
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


if __name__ == "__main__":
    app.run(ssl_context="adhoc", port=9994)
