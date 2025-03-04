import weave
from weave.trace.weave_client import WeaveClient


def generate_objects(weave_client: WeaveClient, obj_count: int, version_count: int):
    for i in range(obj_count):
        for j in range(version_count):
            weave.publish({"i": i, "j": j}, name=f"obj_{i}")


def test_get_versions(client):
    """Test the get_versions method of the WeaveClient class."""
    generate_objects(client, obj_count=5, version_count=3)

    versions = client.get_versions("obj_0")
    assert len(versions) == 3

    non_existent_versions = client.get_versions("non_existent_object_id")
    assert len(non_existent_versions) == 0
