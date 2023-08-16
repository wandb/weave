from weave import serialize, storage
from weave.server import handle_request
import base64
import zlib
import json


def test_graph_playback():
    for payload in execute_payloads:
        res = handle_request(payload, True, storage.make_js_serializer())
        res.results.unwrap()


def test_zlib_playback():
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
zlib_str = "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"

# Paste graphs below (from DD or Network tab to test)
execute_payloads: list[dict] = []
