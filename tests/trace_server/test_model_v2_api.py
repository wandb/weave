"""Tests for Model V2 API endpoints.

This module tests the V2 API endpoints for Models:
- Create
- Read
- List
- Delete

The tests run against both SQLite and ClickHouse backends.
"""

from weave.trace_server import trace_server_interface as tsi


class TestModelsV2API:
    """Tests for Models V2 API endpoints."""

    def test_model_create_v2(self, client):
        """Test creating a model via V2 API."""
        project_id = client._project_id()

        # Create a model
        req = tsi.ModelCreateV2Req(
            project_id=project_id,
            name="TestModel",
            description="A test model",
            source_code="""import weave

class TestModel(weave.Model):
    temperature: float = 0.7

    @weave.op()
    def predict(self, input: str) -> dict:
        return {"output": f"Processed: {input}"}
""",
            attributes={"temperature": 0.7},
        )
        res = client.server.model_create_v2(req)

        # Verify response
        assert res.object_id == "model_testmodel"
        assert res.digest is not None
        assert res.version_index == 0
        assert res.model_ref is not None

    def test_model_read_v2(self, client):
        """Test reading a model via V2 API."""
        project_id = client._project_id()

        # Create a model first
        source_code = """import weave

class MyTestModel(weave.Model):
    prompt: str = "Hello"

    @weave.op()
    def predict(self, input: str) -> str:
        return f"{self.prompt} {input}"
"""
        create_req = tsi.ModelCreateV2Req(
            project_id=project_id,
            name="ReadableModel",
            description="Model for testing reads",
            source_code=source_code,
            attributes={"prompt": "Hello"},
        )
        create_res = client.server.model_create_v2(create_req)

        # Read the model
        read_req = tsi.ModelReadV2Req(
            project_id=project_id,
            object_id=create_res.object_id,
            digest=create_res.digest,
        )
        read_res = client.server.model_read_v2(read_req)

        # Verify response
        assert read_res.object_id == create_res.object_id
        assert read_res.digest == create_res.digest
        assert read_res.version_index == 0
        assert read_res.name == "ReadableModel"
        assert read_res.description == "Model for testing reads"
        assert read_res.source_code == source_code
        assert read_res.attributes is not None
        assert read_res.attributes.get("prompt") == "Hello"
        assert read_res.created_at is not None

    def test_model_list_v2(self, client):
        """Test listing models via V2 API."""
        project_id = client._project_id()

        # Create multiple models
        for i in range(3):
            req = tsi.ModelCreateV2Req(
                project_id=project_id,
                name=f"ListTestModel{i}",
                source_code=f"""import weave

class ListTestModel{i}(weave.Model):
    @weave.op()
    def predict(self):
        return {i}
""",
            )
            client.server.model_create_v2(req)

        # List models
        list_req = tsi.ModelListV2Req(project_id=project_id)
        models = list(client.server.model_list_v2(list_req))

        # Verify we get at least our 3 models
        assert len(models) >= 3
        model_names = [m.name for m in models]
        assert "ListTestModel0" in model_names
        assert "ListTestModel1" in model_names
        assert "ListTestModel2" in model_names

    def test_model_list_v2_with_limit(self, client):
        """Test listing models with limit via V2 API."""
        project_id = client._project_id()

        # Create multiple models
        for i in range(5):
            req = tsi.ModelCreateV2Req(
                project_id=project_id,
                name=f"LimitTestModel{i}",
                source_code=f"""import weave

class LimitTestModel{i}(weave.Model):
    @weave.op()
    def predict(self):
        return {i}
""",
            )
            client.server.model_create_v2(req)

        # List models with limit
        list_req = tsi.ModelListV2Req(project_id=project_id, limit=2)
        models = list(client.server.model_list_v2(list_req))

        # Verify limit is respected
        assert len(models) == 2

    def test_model_delete_v2(self, client):
        """Test deleting a model via V2 API."""
        project_id = client._project_id()

        # Create a model
        create_req = tsi.ModelCreateV2Req(
            project_id=project_id,
            name="DeletableModel",
            source_code="""import weave

class DeletableModel(weave.Model):
    @weave.op()
    def predict(self):
        pass
""",
        )
        create_res = client.server.model_create_v2(create_req)

        # Delete the model
        delete_req = tsi.ModelDeleteV2Req(
            project_id=project_id,
            object_id=create_res.object_id,
            digests=[create_res.digest],
        )
        delete_res = client.server.model_delete_v2(delete_req)

        # Verify deletion
        assert delete_res.num_deleted == 1

    def test_model_delete_v2_all_versions(self, client):
        """Test deleting all versions of a model via V2 API."""
        project_id = client._project_id()

        # Create multiple versions
        digests = []
        for i in range(3):
            create_req = tsi.ModelCreateV2Req(
                project_id=project_id,
                name="MultiVersionModel",
                source_code=f"""import weave

class MultiVersionModel(weave.Model):
    version: int = {i}

    @weave.op()
    def predict(self):
        return {i}
""",
            )
            create_res = client.server.model_create_v2(create_req)
            digests.append(create_res.digest)

        # Delete all versions (None means delete all)
        delete_req = tsi.ModelDeleteV2Req(
            project_id=project_id,
            object_id="model_multiversionmodel",
            digests=None,
        )
        delete_res = client.server.model_delete_v2(delete_req)

        # Verify all versions deleted
        assert delete_res.num_deleted == 3

    def test_model_versioning_workflow(self, client):
        """Test that versioning works correctly for models."""
        project_id = client._project_id()

        # Create multiple versions of the same model
        versions = []
        for i in range(3):
            req = tsi.ModelCreateV2Req(
                project_id=project_id,
                name="VersionedModel",
                source_code=f"""import weave

class VersionedModel(weave.Model):
    version: int = {i}

    @weave.op()
    def predict(self):
        return {i}
""",
            )
            res = client.server.model_create_v2(req)
            versions.append(res)

        # Verify version indexes
        assert versions[0].version_index == 0
        assert versions[1].version_index == 1
        assert versions[2].version_index == 2

        # Verify all versions have different digests
        assert versions[0].digest != versions[1].digest
        assert versions[1].digest != versions[2].digest
        assert versions[0].digest != versions[2].digest

        # Verify we can read each version
        for version in versions:
            read_req = tsi.ModelReadV2Req(
                project_id=project_id,
                object_id=version.object_id,
                digest=version.digest,
            )
            read_res = client.server.model_read_v2(read_req)
            assert read_res.digest == version.digest
            assert read_res.version_index == version.version_index

    def test_model_with_complex_attributes(self, client):
        """Test creating a model with complex attributes."""
        project_id = client._project_id()

        # Create a model with complex attributes
        req = tsi.ModelCreateV2Req(
            project_id=project_id,
            name="ComplexModel",
            description="Model with complex attributes",
            source_code="""import weave

class ComplexModel(weave.Model):
    temperature: float = 0.8
    max_tokens: int = 100
    system_prompt: str = "You are helpful"

    @weave.op()
    def predict(self, input: str) -> str:
        return f"Temp {self.temperature}: {input}"
""",
            attributes={
                "temperature": 0.8,
                "max_tokens": 100,
                "system_prompt": "You are helpful",
            },
        )
        res = client.server.model_create_v2(req)

        # Read it back and verify attributes
        read_req = tsi.ModelReadV2Req(
            project_id=project_id,
            object_id=res.object_id,
            digest=res.digest,
        )
        read_res = client.server.model_read_v2(read_req)

        assert read_res.attributes is not None
        assert read_res.attributes.get("temperature") == 0.8
        assert read_res.attributes.get("max_tokens") == 100
        assert read_res.attributes.get("system_prompt") == "You are helpful"

    def test_model_with_no_attributes(self, client):
        """Test creating a model without additional attributes."""
        project_id = client._project_id()

        # Create a simple model
        req = tsi.ModelCreateV2Req(
            project_id=project_id,
            name="SimpleModel",
            source_code="""import weave

class SimpleModel(weave.Model):
    @weave.op()
    def predict(self, x: int) -> int:
        return x * 2
""",
        )
        res = client.server.model_create_v2(req)

        # Read it back
        read_req = tsi.ModelReadV2Req(
            project_id=project_id,
            object_id=res.object_id,
            digest=res.digest,
        )
        read_res = client.server.model_read_v2(read_req)

        assert read_res.name == "SimpleModel"
        # Attributes should be None or empty
        assert read_res.attributes is None or len(read_res.attributes) == 0
