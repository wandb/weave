import queue
import threading
import time

import pytest
import requests
from flask import Flask

import weave


@pytest.fixture
def flask_server(client):
    app = Flask(__name__)
    server_port = 6789
    host = "127.0.0.1"

    @app.route("/")
    def index():
        d = weave.Dataset(rows=[{"a": 5, "b": 6}, {"a": 7, "b": 10}])
        ref = weave.publish(d)
        return ref.digest

    def run_server():
        # Using Flask's built-in development server
        app.run(host=host, port=server_port, threaded=True, use_reloader=False)

    thread = threading.Thread(target=run_server, daemon=True)
    thread.start()
    time.sleep(2)

    url = f"http://{host}:{server_port}/"
    yield url


def test_flask_server(flask_server):
    url = flask_server
    response = requests.get(url)
    assert response.status_code == 200
    assert response.text == "0xTDJ6hEmsx8Wg9H75y42bL2WgvW5l4IXjuhHcrMh7A"


def test_weave_client_global_accessible_in_thread(client):
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
