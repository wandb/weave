import queue
import threading

import httpx
import pytest
from flask import Flask
from werkzeug.serving import make_server

import weave
from tests.trace.util import NOT_CLICKHOUSE_BACKEND


@pytest.fixture
def flask_server(weave_active):
    app = Flask(__name__)
    host = "127.0.0.1"

    @app.route("/")
    def index():
        d = weave.Dataset(rows=[{"a": 5, "b": 6}, {"a": 7, "b": 10}])
        ref = weave.publish(d)
        return ref.digest

    server = make_server(host, 0, app, threaded=True)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://{host}:{server.server_port}/"
    finally:
        server.shutdown()
        thread.join()
        server.server_close()


@pytest.mark.skipif(
    NOT_CLICKHOUSE_BACKEND,
    reason="requires a served HTTP backend; the in-process fake client is not "
    "reachable from werkzeug request threads",
)
def test_flask_server(flask_server):
    url = flask_server
    with httpx.Client() as client:
        response = client.get(url)
    assert response.status_code == 200
    assert response.text == "FkWFKCRcl9wsGp3yclN7v1IIAICTPenpZYrWo0otI4Y"


def test_weave_client_global_accessible_in_thread(weave_active):
    def thread_func(q: queue.Queue):
        try:
            d = weave.Dataset(rows=[{"a": 5, "b": 6}, {"a": 7, "b": 10}])
            ref = weave.publish(d)
            q.put((None, ref))
        except Exception as e:
            q.put((e, None))

    q = queue.Queue()
    thread = threading.Thread(target=thread_func, args=(q,))
    thread.start()
    thread.join()

    error, _ = q.get()
    if error:
        raise error
