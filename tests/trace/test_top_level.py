import weave
from weave.trace.weave_client import WeaveClient


def test_get_client(client: WeaveClient):
    assert weave.get_client() is client


def test_get_client_no_client():
    assert weave.get_client() is None
