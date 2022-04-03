import numpy as np
import contextlib
import pytest
from . import api as weave
from .weave_internal import make_const_node
from . import ops
import os
from . import storage
from . import client as _client
from . import server as _server

SERVER_TYPES = ["inprocess", "subprocess", "http"]

# Python seems to take forever to spin up a new Process (maybe
# pytest slows it down?). So just spin up the subprocess server once
subprocess_server = None


def setup_module():
    global subprocess_server
    subprocess_server = _server.SubprocessServerClient()


def teardown_module():
    subprocess_server.shutdown()


@contextlib.contextmanager
def client(server_type):
    if server_type == "inprocess":
        yield _client.Client(_server.InProcessServer())
    elif server_type == "subprocess":
        yield _client.Client(subprocess_server)
    elif server_type == "http":
        port = 9995
        server = _server.HttpServer(port)
        server.start()
        yield _client.Client(_server.HttpServerClient("http://127.0.0.1:%s" % port))
        server.shutdown()


@pytest.mark.parametrize("server_type", SERVER_TYPES)
@pytest.mark.timeout(2)
def test_basic(server_type):
    with client(server_type) as wc:
        nine = make_const_node(weave.types.Number(), 9)
        assert weave.use(nine + 3, client=wc) == 12


# copied from test_image
@pytest.mark.parametrize("server_type", SERVER_TYPES)
@pytest.mark.timeout(2)
def test_local_artifact_ops(server_type):
    with client(server_type) as wc:
        im = ops.image.WBImage.from_numpy(np.ones((5, 5)))
        ref = storage.save(im)

        la = ops.artifacts.local_artifact(ref.artifact._name, ref.artifact.version)
        im2_node = la.get("_obj")

        url_node = im2_node.url()
        url = weave.use(url_node, client=wc)
        without_prefix = url[len("file://") :]

        assert os.path.exists(without_prefix)


@pytest.mark.parametrize("server_type", SERVER_TYPES)
@pytest.mark.timeout(2)
def test_type_returning_op(server_type):
    with client(server_type) as wc:
        csv_type = weave.use(
            ops.local_path_return_type("testdata/cereal.csv"), client=wc
        )
        assert csv_type.name == "local_file"
