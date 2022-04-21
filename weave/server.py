from flask import current_app
from werkzeug.serving import make_server
import multiprocessing
import threading
import time
import requests
import traceback
import viztracer

from . import graph, util as _util, client as _client
from . import serialize
from . import forward_graph
from . import storage


is_tracing = True


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
    # print("Server request running nodes")
    """
    for node in nodes:
        print(graph.node_expr_str(node))
    """
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
    def __init__(self, url):
        self.url = url

    def execute(self, nodes, no_cache=False):
        serialized = serialize.serialize(nodes)
        r = requests.post(self.url + "/__weave/execute/v2", json={"graphs": serialized})
        r.raise_for_status()

        response = r.json()["data"]
        deserialized = [storage.from_python(r) for r in response]
        return [storage.deref(r) for r in deserialized]


class ServerInterface(object):
    def start(self):
        raise NotImplementedError()

    def shutdown(self):
        raise NotImplementedError()

    @property
    def url(self):
        raise NotImplementedError()


class HttpServerInternal(object):
    def __init__(self, port=0, host="127.0.0.1"):
        from . import weave_server

        self.host = host

        app = weave_server.app

        self.srv = make_server(host, port, app, threaded=False)

        # if the passed port is zero then a randomly allocated port will be used. this
        # gets the value of the port that was assigned
        self.port = self.srv.socket.getsockname()[1]

    def serve(self):
        self.srv.serve_forever()

    def shutdown(self):
        self.srv.shutdown()

    @property
    def url(self):
        url = f"http://{self.host}"
        if self.port is not None:
            url = f"{url}:{self.port}"
        return url


class HttpServerThread(threading.Thread, ServerInterface):
    def __init__(self, port=0, host="127.0.0.1"):
        threading.Thread.__init__(self, daemon=True)
        self.server = HttpServerInternal(port, host)

    def run(self):
        self.server.serve()

    def shutdown(self):
        self.server.shutdown()

    @property
    def url(self):
        return self.server.url


def server_proc(port, host):
    server = HttpServerInternal(port, host)
    server.serve()
    return server


class HttpServer(ServerInterface):
    def __init__(self, port=0, host="127.0.0.1"):
        if port == 0:
            port = 9994
        self.port = port
        self.host = host
        self.proc = multiprocessing.Process(
            target=server_proc,
            args=(
                self.port,
                self.host,
            ),
        )

    def start(self):
        self.proc.start()
        # TODO: stop being lazy
        time.sleep(3)

    def shutdown(self):
        server = self.proc.join()
        server.shutdown()

    @property
    def url(self):
        url = f"http://{self.host}"
        if self.port is not None:
            url = f"{url}:{self.port}"
        return url
