from __future__ import print_function

import os
import typing
import logging

from flask import current_app
from werkzeug.serving import make_server
import multiprocessing
import threading
import time
import requests
import traceback
import viztracer
import time
import cProfile

from weave.language_features.tagging.tag_store import isolated_tagging_context

from . import execute
from . import serialize
from . import storage
from . import context
from . import util
from . import graph_debug


PROFILE = False

is_tracing = True

OptionalAuthType = typing.Optional[
    typing.Union[typing.Tuple[str, str], requests.models.HTTPBasicAuth]
]

logger = logging.getLogger("root")


def _handle_request(request, deref=False):

    global is_tracing
    start_time = time.time()
    request_trace = not is_tracing
    if request_trace:
        is_tracing = True
        tracer = viztracer.VizTracer()
        tracer.start()
    nodes = serialize.deserialize(request["graphs"])

    with context.execution_client():
        result = execute.execute_nodes(
            nodes, no_cache=util.parse_boolean_env_var("WEAVE_NO_CACHE")
        )
    if deref:
        result = [storage.deref(r) for r in result]
    # print("Server request %s (%0.5fs): %s..." % (start_time,
    #                                              time.time() - start_time, [n.from_op.name for n in nodes[:3]]))
    if request_trace:
        is_tracing = False
        tracer.stop()
        tracer.save(output_file="request_%s.json" % time.time())

    # Forces output to be untagged
    with isolated_tagging_context():
        result = [storage.to_python(r) for r in result]

    logger.info("Server request done in: %ss" % (time.time() - start_time))
    return result


def handle_request(request, deref=False):
    if not PROFILE:
        return _handle_request(request, deref=deref)
    with cProfile.Profile() as pr:
        res = _handle_request(request, deref=deref)
    pr.dump_stats("/tmp/weave/profile-%s" % time.time())
    return res


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


def capture_weave_server_logs(log_level=logging.DEBUG):
    from . import weave_server

    weave_server.enable_stream_logging(log_level)
