from PIL import Image

import weave
from weave.trace import serialize


def test_serialize_caching(client):
    serialize._custom_weave_type_cache_map[client._project_id()].reset()
    img = Image.new("RGB", (100, 100))
    serialized_img = serialize._to_json_custom_weave_type(
        img, client._project_id(), client.server
    )
    client._flush()
    access_log = client.server.attribute_access_log
    methods_1 = [log for log in access_log if not log.startswith("_")]
    assert methods_1 == [
        "ensure_project_exists",  # default initialization
        "file_create",  # creates the deserialize op code
        "obj_create",  # creates the deserialize op object
        "file_create",  # creates the image file
    ]

    # Serialize again
    serialized_img = serialize._to_json_custom_weave_type(
        img, client._project_id(), client.server
    )
    client._flush()
    access_log = client.server.attribute_access_log
    methods_2 = [log for log in access_log if not log.startswith("_")]
    # No new methods should be called!
    assert methods_2 == methods_1

    # Make sure we can deserialize
    deserialize_img = serialize._from_json_custom_weave_type(
        serialized_img, client._project_id(), client.server
    )
    assert isinstance(deserialize_img, Image.Image)
    assert deserialize_img.tobytes() == img.tobytes()

    # Again, no new methods should be called!
    client._flush()
    access_log = client.server.attribute_access_log
    methods_3 = [log for log in access_log if not log.startswith("_")]
    assert methods_3 == methods_2

    # Reset the cache
    serialize._custom_weave_type_cache_map[client._project_id()].reset()

    # Deserialize should trigger new methods
    deserialize_img = serialize._from_json_custom_weave_type(
        serialized_img, client._project_id(), client.server
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
    serialized_img = serialize._to_json_custom_weave_type(
        deserialize_img, client._project_id(), client.server
    )
    client._flush()
    access_log = client.server.attribute_access_log
    methods_5 = [log for log in access_log if not log.startswith("_")]
    assert methods_5 == methods_4
