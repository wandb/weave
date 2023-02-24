from __future__ import print_function

import typing
import logging

from flask import current_app
from werkzeug.serving import make_server
import multiprocessing
import threading
import time
import requests
import traceback
import time


from weave.language_features.tagging.tag_store import isolated_tagging_context

from . import execute
from . import serialize
from . import storage
from . import context
from . import weave_types
from . import engine_trace
from . import logs


# A function to monkeypatch the request post method
# def patch_request_post():
#     r_post = requests.post

#     logging.info = lambda *args, **kwargs: None
#     logging.warn = lambda *args, **kwargs: None
#     logging.debug = lambda *args, **kwargs: None

#     def post(*args, **kwargs):
#         logging.critical(kwargs["json"]["query"].split(' ')[1])
#         return r_post(*args, **kwargs)

#     requests.post = post

# patch_request_post()

PROFILE = False

OptionalAuthType = typing.Optional[
    typing.Union[typing.Tuple[str, str], requests.models.HTTPBasicAuth]
]

logger = logging.getLogger("root")


def handle_request(request, deref=False, serialize_fn=storage.to_python):
    start_time = time.time()
    tracer = engine_trace.tracer()
    # nodes = [graph.Node.node_from_json(n) for n in request["graphs"]]
    with tracer.trace("request:deserialize"):
        nodes = serialize.deserialize(request["graphs"])

    with tracer.trace("request:execute"):
        with context.execution_client():
            result = execute.execute_nodes(nodes)
    with tracer.trace("request:deref"):
        if deref:
            result = [
                r if isinstance(n.type, weave_types.RefType) else storage.deref(r)
                for (n, r) in zip(nodes, result)
            ]
    # print("Server request %s (%0.5fs): %s..." % (start_time,
    #                                              time.time() - start_time, [n.from_op.name for n in nodes[:3]]))

    # Forces output to be untagged
    with tracer.trace("serialize_response"):
        with isolated_tagging_context():
            result = [serialize_fn(r) for r in result]

    logger.info("Server request done in: %ss" % (time.time() - start_time))
    return result


class SubprocessServer(multiprocessing.Process):
    def __init__(self, req_queue, resp_queue):
        multiprocessing.Process.__init__(self)
        self.req_queue = req_queue
        self.resp_queue = resp_queue

    def run(self):
        while True:
            req = self.req_queue.get()
            try:
                resp = handle_request(req)
                self.resp_queue.put(resp)
            except:
                print("Weave subprocess server error")
                traceback.print_exc()
                self.resp_queue.put(Exception("Caught exception in sub-process server"))
                break

    def shutdown(self):
        self.kill()


class SubprocessServerClient:
    def __init__(self):
        self.req_queue = multiprocessing.Queue()
        self.resp_queue = multiprocessing.Queue()
        self.server_proc = SubprocessServer(self.req_queue, self.resp_queue)
        self.server_proc.start()

    def shutdown(self):
        self.server_proc.shutdown()

    def execute(self, nodes, no_cache=False):
        self.req_queue.put({"graphs": serialize.serialize(nodes)})
        response = self.resp_queue.get()
        deserialized = [storage.from_python(r) for r in response]
        return [storage.deref(r) for r in deserialized]


class InProcessServer(object):
    def __init__(self):
        pass

    def execute(self, nodes, no_cache=False):
        return execute.execute_nodes(nodes, no_cache=no_cache)


class HttpServerClient(object):
    def __init__(self, url, emulate_weavejs=False, auth: OptionalAuthType = None):
        """Constructor.

        Args:
            url: The server base url
            emulate_weavejs: For testing only, should not be used from user code.
            auth (optional): auth argument to `requests.post`
        """
        self.url = url
        self.emulate_weavejs = emulate_weavejs
        self.execute_endpoint = "/__weave/execute/v2"
        self.auth = auth
        if emulate_weavejs:
            self.execute_endpoint = "/__weave/execute"

    def execute(self, nodes, no_cache=False):
        serialized = serialize.serialize(nodes)
        r = requests.post(
            self.url + self.execute_endpoint,
            json={"graphs": serialized},
            auth=self.auth,
        )
        r.raise_for_status()

        response = r.json()["data"]

        if self.emulate_weavejs:
            # When emulating weavejs, just return the server's json response.
            return response

        deserialized = [storage.from_python(r) for r in response]
        return [storage.deref(r) for r in deserialized]


class HttpServer(threading.Thread):
    def __init__(self, port=0, host="127.0.0.1"):
        from . import weave_server

        self.host = host

        app = weave_server.app
        threading.Thread.__init__(self, daemon=True)
        self.srv = make_server(host, port, app, threaded=False)

        # if the passed port is zero then a randomly allocated port will be used. this
        # gets the value of the port that was assigned
        self.port = self.srv.socket.getsockname()[1]

    def run(self):
        self.srv.serve_forever()

    def shutdown(self):
        self.srv.shutdown()

    @property
    def url(self):
        url = f"http://{self.host}"
        if self.port is not None:
            url = f"{url}:{self.port}"
        return url


def capture_weave_server_logs(log_level: str = "INFO"):
    logs.enable_stream_logging(
        logger,
        wsgi_stream_settings=logs.LogSettings(logs.LogFormat.PRETTY, log_level),
    )
