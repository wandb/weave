import weave
from weave.trace_server.trace_server_interface import SortBy


class TestModel(weave.Object):
    value: int


def test_object_group_caching(client_creator, mocker):
    with client_creator() as client:
        # Create test object
        obj = TestModel(value=1)
        ref = client._save_object(obj, "test-obj")

        # Get two separate group instances for the same object
        groups1 = client.get_objects()
        groups2 = client.get_objects()
        group1 = groups1[0]
        group2 = groups2[0]

        # Mock get_object_versions to track calls
        mock_get_versions = mocker.patch.object(
            client, "get_object_versions", wraps=client.get_object_versions
        )

        # First call on group1 should hit server
        versions1 = group1.get_versions()
        assert mock_get_versions.call_count == 1
        assert len(versions1) == 1
        assert versions1[0].value == 1

        # Second call on group1 should use cache
        versions2 = group1.get_versions()
        assert mock_get_versions.call_count == 1  # Count shouldn't increase
        assert versions2 == versions1

        # Call on group2 should hit server again (separate cache)
        versions3 = group2.get_versions()
        assert mock_get_versions.call_count == 2
        assert versions3 == versions1

        # Different parameters should hit server again
        versions4 = group1.get_versions(limit=10)
        assert mock_get_versions.call_count == 3

        # Same parameters should use cache
        versions5 = group1.get_versions(limit=10)
        assert mock_get_versions.call_count == 3
        assert versions5 == versions4

        # Different sort should hit server
        versions6 = group1.get_versions(
            sort_by=[SortBy(field="version_index", direction="desc")]
        )
        assert mock_get_versions.call_count == 4

        # Test cache invalidation by adding new version
        obj2 = TestModel(value=2)
        ref2 = client._save_object(obj2, "test-obj")
        group1.invalidate_cache()
        group2.invalidate_cache()

        # Should hit server again even with cached params
        versions7 = group1.get_versions()
        assert mock_get_versions.call_count == 5
        assert len(versions7) == 2
