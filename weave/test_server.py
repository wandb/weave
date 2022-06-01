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

import requests

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
@pytest.mark.timeout(3)
def test_basic(server_type):
    with client(server_type) as wc:
        nine = make_const_node(weave.types.Number(), 9)
        assert weave.use(nine + 3, client=wc) == 12


@pytest.mark.parametrize("server_type", SERVER_TYPES)
@pytest.mark.timeout(3)
def test_type_returning_op(server_type):
    with client(server_type) as wc:
        csv_type = weave.use(
            ops.local_path_return_type("testdata/cereal.csv"), client=wc
        )
        assert csv_type.name == "local_file"


@pytest.mark.timeout(3)
def test_500_does_raise_jsondecode_error_from_http_server():
    with client("http") as wc:

        @weave.op()
        def custom_op_that_should_return_500(x: str) -> str:
            if x == "abcd":
                raise ValueError("returning 500")
            return x + "a"

        # should not raise json decoder error, but an HTTP error insteard
        with pytest.raises(requests.exceptions.HTTPError):
            weave.use(custom_op_that_should_return_500("abcd"), client=wc)
