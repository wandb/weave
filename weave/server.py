from __future__ import print_function

import typing

from flask import current_app
from werkzeug.serving import make_server
import multiprocessing
import threading
import time
import requests
import traceback
import viztracer
import time

from . import graph, util as _util, client as _client
from . import serialize
from . import forward_graph
from . import storage


import sys


is_tracing = True

OptionalAuthType = typing.Optional[
    typing.Union[typing.Tuple[str, str], requests.models.HTTPBasicAuth]
]


def handle_request(request, deref=False):
    from . import execute

    global is_tracing
    start_time = time.time()
    request_trace = not is_tracing
    if request_trace:
        is_tracing = True
        tracer = viztracer.VizTracer()
        tracer.start()
    nodes = serialize.deserialize(request["graphs"])

    start_time = time.time()
    print("Server request running %s nodes" % len(nodes))
    # """
    for node in nodes:
        print(graph.node_expr_str(node))
    # """
    result = execute.execute_nodes(nodes)
    if deref:
        result = [storage.deref(r) for r in result]
    # print("Server request %s (%0.5fs): %s..." % (start_time,
    #                                              time.time() - start_time, [n.from_op.name for n in nodes[:3]]))
    if request_trace:
        is_tracing = False
        tracer.stop()
        tracer.save(output_file="request_%s.json" % time.time())
    result = [storage.to_python(r) for r in result]
    print("Server request done in: %ss" % (time.time() - start_time))
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
        from . import execute

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
