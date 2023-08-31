from weave import serialize, storage
from weave.server import handle_request
import base64
import zlib
import json


def test_graph_playback():
    for payload in execute_payloads:
        res = handle_request(payload, True, storage.make_js_serializer())
        res.results.unwrap()


def test_zlib_playback(use_server_gql_schema):
    if zlib_str == "":
        return
    req_bytes = zlib.decompress(base64.b64decode(zlib_str.encode("ascii")))
    json_data = json.loads(req_bytes)

    if filter_node != "":
        nodes = serialize.deserialize(json_data["graphs"])
        use_node = None
        for ndx, n in enumerate(nodes):
            if str(n) == filter_node:
                use_node = ndx
                break
        if use_node is None:
            raise Exception("Did not find filter node")
        json_data["graphs"]["targetNodes"] = [
            json_data["graphs"]["targetNodes"][use_node]
        ]

    execute_args = {
        "request": json_data,
        "deref": True,
        "serialize_fn": storage.make_js_serializer(),
    }

    response = handle_request(**execute_args)
    response.results.unwrap()


# (Only used in zlib test) - if you are testing a `WeaveNullishResponseException`, you can
# paste the stringified error node here and we will only execute that node.
filter_node = ""

# Paste zlib below (from DD)
zlib_str = ""

# Paste graphs below (from DD or Network tab to test)
execute_payloads: list[dict] = []
