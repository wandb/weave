import json

from weave.trace import serialize, serializer
from weave.trace.custom_objs import MemTraceFilesArtifact


class MyCustomClass:
    def __init__(self, value):
        self.value = value


def save(obj: MyCustomClass, artifact: MemTraceFilesArtifact, name: str) -> None:
    with artifact.new_file("obj.json", binary=True) as f:
        f.write(json.dumps({"value": obj.value}).encode("utf-8"))


def load(artifact: MemTraceFilesArtifact, name: str) -> MyCustomClass:
    with open(artifact.path("obj.json"), "r") as f:
        return MyCustomClass(json.load(f)["value"])


serializer.register_serializer(MyCustomClass, save, load)


def test_serialize_caching(client):
    # Technically, we could use PIL images in this test, but I like
    # the purity of not having external dependencies in our tests.
    # Furthermore, when running with other tests, it is possible
    # that they will have already serialized this object, and
    # so our tests should be resilient to that.
    obj = MyCustomClass(1)
    serialized_obj = serialize._to_json_custom_weave_type(
        obj, client._project_id(), client.server
    )
    client._flush()
    access_log = client.server.attribute_access_log
    methods_1 = [log for log in access_log if not log.startswith("_")]
    assert methods_1 == [
        "ensure_project_exists",  # default initialization
        "file_create",  # creates the serialized op code
        "obj_create",  # creates the serialized op object
        "file_create",  # creates the custom object file
    ]

    # Serialize again
    serialized_obj = serialize._to_json_custom_weave_type(
        obj, client._project_id(), client.server
    )
    client._flush()
    access_log = client.server.attribute_access_log
    methods_2 = [log for log in access_log if not log.startswith("_")]
    # No new methods should be called!
    assert methods_2 == methods_1

    # Make sure we can deserialize
    deserialize_obj = serialize._from_json_custom_weave_type(
        serialized_obj, client._project_id(), client.server
    )
    assert isinstance(deserialize_obj, MyCustomClass)
    assert deserialize_obj.value == obj.value

    # Again, no new methods should be called!
    client._flush()
    access_log = client.server.attribute_access_log
    methods_3 = [log for log in access_log if not log.startswith("_")]
    assert methods_3 == methods_2

    # Reset the cache
    serialize._custom_weave_type_cache_map[client._project_id()].reset()

    # Deserialize should trigger new methods
    deserialize_obj = serialize._from_json_custom_weave_type(
        serialized_obj, client._project_id(), client.server
    )
    client._flush()
    access_log = client.server.attribute_access_log
    methods_4 = [log for log in access_log if not log.startswith("_")]
    assert methods_4 == methods_3 + [
        "file_content_read",  # load the deserializer
        "obj_read",  # load the image dict
        "file_content_read",  # load the image bytes
    ]

    # Reserialize should not trigger any new methods
    serialized_obj = serialize._to_json_custom_weave_type(
        deserialize_obj, client._project_id(), client.server
    )
    client._flush()
    access_log = client.server.attribute_access_log
    methods_5 = [log for log in access_log if not log.startswith("_")]
    assert methods_5 == methods_4
