from weave import serialize, storage
from weave.server import handle_request
import base64
import zlib
import json


def test_graph_playback():
    for payload in execute_payloads:
        res = handle_request(payload, True, storage.make_js_serializer())
        assert "err" not in res


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
    assert "err" not in response


# (Only used in zlib test) - if you are testing a `WeaveNullishResponseException`, you can
# paste the stringified error node here and we will only execute that node.
filter_node = ""

# Paste zlib below (from DD)
zlib_str = "eJzdVU1v4yAQ/Ssrzo4CGPx13V566V5yW1UVxtihccDCeLVR5P++4Ni7TtPmQ+leerERM/Nm5j0Y9qAyrFm3INsDpQvhFj8Pq9WuESADurNNZ0EASqO3PxqQoQDYg4mpnduXhVvGMUlhGoYUYkhTnIA+cChs691a4cOlcjBDmlbUJchwAH6x2sGRABit7QszlTMj2g+h/wrgWrUe4JB0PyUvO8Wt1GqC9t4evg/GklfH/pZVlSg8Dqvm2+5XPEjuMzRGN8LY3QTlgAvx+/ta8E2jpbLO3X9dgb70bujNGqmqaWsi8SPqyNveTj1O+vy/dU/yIQIhJTBKMEkIInP5Gsk3R/rp/BVkNAAbsXN6hRd7iq7u6VNaVd02F2be7X2k3YrDdf3C5kdjIhnDMIIpjgnFYYIwnpM8JD9imRkDsjgYLRnCF3lOTniu5XBznGCCX3sfvqgGkwh+TMEooihEUZJANBfB07XgRjArHo8LWTkyTsRJLyqC4KdIctdVv5ewEGNCE+JYI5DEYTonrHoz2TsjXdPo/ASfcowTE9Sas3rBjJUl4zZbLpeeo6xrhVngGEUp4jklRV6KJEeYRpCUApVxHtOQL/0sOp9tPIpjNnhTaQdWbgpxj9033ZyPuU6S3DDF1+++MX9NV5HkIp/9mTJOrqfxiYfPff8HAIWm+g=="

# Paste graphs below (from DD or Network tab to test)
execute_payloads: list[dict] = []
