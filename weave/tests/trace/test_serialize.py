from PIL import Image

import weave
from weave.trace import serialize


def test_serialize_caching(client):
    img = Image.new("RGB", (100, 100))
    serialized_img = serialize._to_json_custom_weave_type(
        img, client._project_id(), client.server
    )
    access_log = client.server.attribute_access_log
    assert "files_create" not in access_log
