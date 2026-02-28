"""Tests for Trace Server V2 API endpoints.

This module tests the V2 API endpoints for:
- Ops (create, read, list, delete)
- Datasets (create, read, list, delete)
- Scorers (create, read, list, delete)
- Evaluations (create, read, list, delete)
- Models (create, read, list, delete)
- Evaluation Runs (create, read, list, delete, finish)
- Predictions (create, read, list, delete)
- Scores (create, read, list, delete)

The tests run against both SQLite and ClickHouse backends.
"""

import asyncio
import datetime

import pytest

import weave
from weave.evaluation.eval_imperative import EvaluationLogger
from weave.trace_server import constants
from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.ids import generate_id
from weave.utils.project_id import from_project_id


class TestOpsV2API:
    """Tests for Ops V2 API endpoints."""

    def test_op_create(self, client):
        """Test creating an op via V2 API."""
        project_id = client._project_id()

        # Create an op
        req = tsi.OpCreateReq(
            project_id=project_id,
            name="test_op",
            source_code="def test_op():\n    return 42",
        )
        res = client.server.op_create(req)

        # Verify response
        assert res.object_id == "test_op"
        assert res.digest is not None
        assert res.version_index == 0

    def test_op_read(self, client):
        """Test reading an op via V2 API."""
        project_id = client._project_id()

        # Create an op first
        source_code = "def my_test_op():\n    return 'hello world'"
        create_req = tsi.OpCreateReq(
            project_id=project_id,
            name="readable_op",
            source_code=source_code,
        )
        create_res = client.server.op_create(create_req)

        # Read the op
        read_req = tsi.OpReadReq(
            project_id=project_id,
            object_id="readable_op",
            digest=create_res.digest,
        )
        read_res = client.server.op_read(read_req)

        # Verify response
        assert read_res.object_id == "readable_op"
        assert read_res.digest == create_res.digest
        assert read_res.version_index == 0
        assert read_res.code == source_code
        assert read_res.created_at is not None

    def test_op_list(self, client):
        """Test listing ops via V2 API."""
        project_id = client._project_id()

        # Create multiple ops
        for i in range(3):
            req = tsi.OpCreateReq(
                project_id=project_id,
                name=f"list_test_op_{i}",
                source_code=f"def op_{i}():\n    return {i}",
            )
            client.server.op_create(req)

        # List ops
        list_req = tsi.OpListReq(project_id=project_id)
        ops = list(client.server.op_list(list_req))

        # Verify we get at least our 3 ops
        assert len(ops) >= 3
        op_names = [op.object_id for op in ops]
        assert "list_test_op_0" in op_names
        assert "list_test_op_1" in op_names
        assert "list_test_op_2" in op_names

    def test_op_list_with_limit(self, client):
        """Test listing ops with limit via V2 API."""
        project_id = client._project_id()

        # Create multiple ops
        for i in range(5):
            req = tsi.OpCreateReq(
                project_id=project_id,
                name=f"limit_test_op_{i}",
                source_code=f"def op_{i}():\n    return {i}",
            )
            client.server.op_create(req)

        # List ops with limit
        list_req = tsi.OpListReq(project_id=project_id, limit=2)
        ops = list(client.server.op_list(list_req))

        # Verify limit is respected
        assert len(ops) == 2

    def test_op_delete(self, client):
        """Test deleting an op via V2 API."""
        project_id = client._project_id()

        # Create an op
        create_req = tsi.OpCreateReq(
            project_id=project_id,
            name="deletable_op",
            source_code="def deletable():\n    pass",
        )
        create_res = client.server.op_create(create_req)

        # Delete the op
        delete_req = tsi.OpDeleteReq(
            project_id=project_id,
            object_id="deletable_op",
            digests=[create_res.digest],
        )
        delete_res = client.server.op_delete(delete_req)

        # Verify deletion
        assert delete_res.num_deleted == 1

    def test_op_delete_all_versions(self, client):
        """Test deleting all versions of an op via V2 API."""
        project_id = client._project_id()

        # Create multiple versions
        digests = []
        for i in range(3):
            create_req = tsi.OpCreateReq(
                project_id=project_id,
                name="multi_version_op",
                source_code=f"def multi_version():\n    return {i}",
            )
            create_res = client.server.op_create(create_req)
            digests.append(create_res.digest)

        # Delete all versions (None means delete all)
        delete_req = tsi.OpDeleteReq(
            project_id=project_id,
            object_id="multi_version_op",
            digests=None,
        )
        delete_res = client.server.op_delete(delete_req)

        # Verify all versions deleted
        assert delete_res.num_deleted == 3


class TestDatasetsV2API:
    """Tests for Datasets V2 API endpoints."""

    def test_dataset_create(self, client):
        """Test creating a dataset via V2 API."""
        project_id = client._project_id()

        # Create a dataset
        req = tsi.DatasetCreateReq(
            project_id=project_id,
            name="test_dataset",
            description="A test dataset",
            rows=[
                {"input": "hello", "output": "world"},
                {"input": "foo", "output": "bar"},
            ],
        )
        res = client.server.dataset_create(req)

        # Verify response
        # When name is provided, object_id should be the sanitized name
        assert res.object_id == "test_dataset"
        assert res.digest is not None
        assert res.version_index == 0

    def test_dataset_read(self, client):
        """Test reading a dataset via V2 API."""
        project_id = client._project_id()

        # Create a dataset first
        rows = [
            {"question": "What is 2+2?", "answer": "4"},
            {"question": "What is the capital of France?", "answer": "Paris"},
        ]
        create_req = tsi.DatasetCreateReq(
            project_id=project_id,
            name="readable_dataset",
            description="Test dataset for reading",
            rows=rows,
        )
        create_res = client.server.dataset_create(create_req)

        # Read the dataset
        read_req = tsi.DatasetReadReq(
            project_id=project_id,
            object_id=create_res.object_id,
            digest=create_res.digest,
        )
        read_res = client.server.dataset_read(read_req)

        # Verify response
        assert read_res.object_id == create_res.object_id
        assert read_res.digest == create_res.digest
        assert read_res.version_index == 0
        assert read_res.name == "readable_dataset"
        assert read_res.description == "Test dataset for reading"
        assert read_res.rows is not None  # Field is 'rows', not 'rows_ref'
        assert read_res.created_at is not None

    def test_dataset_list(self, client):
        """Test listing datasets via V2 API."""
        project_id = client._project_id()

        # Create multiple datasets
        for i in range(3):
            req = tsi.DatasetCreateReq(
                project_id=project_id,
                name=f"list_dataset_{i}",
                rows=[{"value": i}],
            )
            client.server.dataset_create(req)

        # List datasets
        list_req = tsi.DatasetListReq(project_id=project_id)
        datasets = list(client.server.dataset_list(list_req))

        # Verify we get at least our 3 datasets
        assert len(datasets) >= 3
        dataset_names = [ds.name for ds in datasets]
        assert "list_dataset_0" in dataset_names
        assert "list_dataset_1" in dataset_names
        assert "list_dataset_2" in dataset_names

    def test_dataset_delete(self, client):
        """Test deleting a dataset via V2 API."""
        project_id = client._project_id()

        # Create a dataset
        create_req = tsi.DatasetCreateReq(
            project_id=project_id,
            name="deletable_dataset",
            rows=[{"data": "test"}],
        )
        create_res = client.server.dataset_create(create_req)

        # Delete the dataset
        delete_req = tsi.DatasetDeleteReq(
            project_id=project_id,
            object_id=create_res.object_id,
            digests=[create_res.digest],
        )
        delete_res = client.server.dataset_delete(delete_req)

        # Verify deletion
        assert delete_res.num_deleted == 1


class TestScorersV2API:
    """Tests for Scorers V2 API endpoints."""

    def test_scorer_create(self, client):
        """Test creating a scorer via V2 API."""
        project_id = client._project_id()

        # Create a scorer
        req = tsi.ScorerCreateReq(
            project_id=project_id,
            name="test_scorer",
            description="A test scorer",
            op_source_code="def score(output, target):\n    return output == target",
        )
        res = client.server.scorer_create(req)

        # Verify response
        # When name is provided, object_id should be the sanitized name
        assert res.object_id == "test_scorer"
        assert res.digest is not None
        assert res.version_index == 0

    def test_scorer_read(self, client):
        """Test reading a scorer via V2 API."""
        project_id = client._project_id()

        # Create a scorer first
        source_code = (
            "def accuracy_score(output, target):\n    return int(output == target)"
        )
        create_req = tsi.ScorerCreateReq(
            project_id=project_id,
            name="accuracy_scorer",
            description="Measures accuracy",
            op_source_code=source_code,
        )
        create_res = client.server.scorer_create(create_req)

        # Read the scorer
        read_req = tsi.ScorerReadReq(
            project_id=project_id,
            object_id=create_res.object_id,
            digest=create_res.digest,
        )
        read_res = client.server.scorer_read(read_req)

        # Verify response
        assert read_res.object_id == create_res.object_id
        assert read_res.digest == create_res.digest
        assert read_res.version_index == 0
        assert read_res.name == "accuracy_scorer"
        assert read_res.description == "Measures accuracy"
        assert read_res.score_op is not None  # ScorerReadRes has 'score_op', not 'code'
        assert read_res.created_at is not None

    def test_scorer_list(self, client):
        """Test listing scorers via V2 API."""
        project_id = client._project_id()

        # Create multiple scorers
        for i in range(3):
            req = tsi.ScorerCreateReq(
                project_id=project_id,
                name=f"list_scorer_{i}",
                op_source_code=f"def scorer_{i}():\n    return {i}",
            )
            client.server.scorer_create(req)

        # List scorers
        list_req = tsi.ScorerListReq(project_id=project_id)
        scorers = list(client.server.scorer_list(list_req))

        # Verify we get at least our 3 scorers
        assert len(scorers) >= 3
        scorer_names = [s.name for s in scorers]
        assert "list_scorer_0" in scorer_names
        assert "list_scorer_1" in scorer_names
        assert "list_scorer_2" in scorer_names

    def test_scorer_delete(self, client):
        """Test deleting a scorer via V2 API."""
        project_id = client._project_id()

        # Create a scorer
        create_req = tsi.ScorerCreateReq(
            project_id=project_id,
            name="deletable_scorer",
            op_source_code="def deletable():\n    pass",
        )
        create_res = client.server.scorer_create(create_req)

        # Delete the scorer
        delete_req = tsi.ScorerDeleteReq(
            project_id=project_id,
            object_id=create_res.object_id,
            digests=[create_res.digest],
        )
        delete_res = client.server.scorer_delete(delete_req)

        # Verify deletion
        assert delete_res.num_deleted == 1


class TestEvaluationsV2API:
    """Tests for Evaluations V2 API endpoints."""

    def test_evaluation_create(self, client):
        """Test creating an evaluation via V2 API."""
        project_id = client._project_id()

        # First create a dataset
        dataset_req = tsi.DatasetCreateReq(
            project_id=project_id,
            name="eval_dataset",
            rows=[{"input": "test", "output": "result"}],
        )
        dataset_res = client.server.dataset_create(dataset_req)

        # Create dataset ref
        entity, project = from_project_id(project_id)
        dataset_ref = f"weave:///{entity}/{project}/object/{dataset_res.object_id}:{dataset_res.digest}"

        # Create an evaluation
        req = tsi.EvaluationCreateReq(
            project_id=project_id,
            name="test_evaluation",
            description="A test evaluation",
            dataset=dataset_ref,
            scorers=[],
            trials=1,
        )
        res = client.server.evaluation_create(req)

        # Verify response
        assert res.object_id == "test_evaluation"  # Evaluations use name as object_id
        assert res.digest is not None
        assert res.version_index == 0
        assert res.evaluation_ref is not None

    def test_evaluation_read(self, client):
        """Test reading an evaluation via V2 API."""
        project_id = client._project_id()

        # Create dataset and evaluation first
        dataset_req = tsi.DatasetCreateReq(
            project_id=project_id,
            name="read_eval_dataset",
            rows=[{"data": "value"}],
        )
        dataset_res = client.server.dataset_create(dataset_req)

        entity, project = from_project_id(project_id)
        dataset_ref = f"weave:///{entity}/{project}/object/{dataset_res.object_id}:{dataset_res.digest}"

        eval_req = tsi.EvaluationCreateReq(
            project_id=project_id,
            name="readable_evaluation",
            description="Test eval for reading",
            dataset=dataset_ref,
            scorers=[],
            trials=2,
            evaluation_name="custom_eval_name",
        )
        eval_res = client.server.evaluation_create(eval_req)

        # Read the evaluation
        read_req = tsi.EvaluationReadReq(
            project_id=project_id,
            object_id=eval_res.object_id,
            digest=eval_res.digest,
        )
        read_res = client.server.evaluation_read(read_req)

        # Verify response
        assert read_res.object_id == eval_res.object_id
        assert read_res.digest == eval_res.digest
        assert read_res.version_index == 0
        assert read_res.name == "readable_evaluation"
        assert read_res.description == "Test eval for reading"
        assert read_res.dataset == dataset_ref
        assert read_res.scorers == []
        assert read_res.trials == 2
        assert read_res.evaluation_name == "custom_eval_name"
        assert read_res.evaluate_op is not None
        assert read_res.predict_and_score_op is not None
        assert read_res.summarize_op is not None
        assert read_res.created_at is not None

    def test_evaluation_list(self, client):
        """Test listing evaluations via V2 API."""
        project_id = client._project_id()

        # Create dataset
        dataset_req = tsi.DatasetCreateReq(
            project_id=project_id,
            name="list_eval_dataset",
            rows=[{"x": 1}],
        )
        dataset_res = client.server.dataset_create(dataset_req)

        entity, project = from_project_id(project_id)
        dataset_ref = f"weave:///{entity}/{project}/object/{dataset_res.object_id}:{dataset_res.digest}"

        # Create multiple evaluations
        for i in range(3):
            req = tsi.EvaluationCreateReq(
                project_id=project_id,
                name=f"list_evaluation_{i}",
                dataset=dataset_ref,
                scorers=[],
            )
            client.server.evaluation_create(req)

        # List evaluations
        list_req = tsi.EvaluationListReq(project_id=project_id)
        evaluations = list(client.server.evaluation_list(list_req))

        # Verify we get at least our 3 evaluations
        assert len(evaluations) >= 3
        eval_names = [ev.name for ev in evaluations]
        assert "list_evaluation_0" in eval_names
        assert "list_evaluation_1" in eval_names
        assert "list_evaluation_2" in eval_names

    def test_evaluation_delete(self, client):
        """Test deleting an evaluation via V2 API."""
        project_id = client._project_id()

        # Create dataset and evaluation
        dataset_req = tsi.DatasetCreateReq(
            project_id=project_id,
            name="delete_eval_dataset",
            rows=[{"data": "test"}],
        )
        dataset_res = client.server.dataset_create(dataset_req)

        entity, project = from_project_id(project_id)
        dataset_ref = f"weave:///{entity}/{project}/object/{dataset_res.object_id}:{dataset_res.digest}"

        eval_req = tsi.EvaluationCreateReq(
            project_id=project_id,
            name="deletable_evaluation",
            dataset=dataset_ref,
            scorers=[],
        )
        eval_res = client.server.evaluation_create(eval_req)

        # Delete the evaluation
        delete_req = tsi.EvaluationDeleteReq(
            project_id=project_id,
            object_id=eval_res.object_id,
            digests=[eval_res.digest],
        )
        delete_res = client.server.evaluation_delete(delete_req)

        # Verify deletion
        assert delete_res.num_deleted == 1

    def test_evaluation_with_scorers(self, client):
        """Test creating an evaluation with scorers."""
        project_id = client._project_id()

        # Create dataset
        dataset_req = tsi.DatasetCreateReq(
            project_id=project_id,
            name="scorer_eval_dataset",
            rows=[{"input": "test", "expected": "output"}],
        )
        dataset_res = client.server.dataset_create(dataset_req)

        # Create scorers
        scorer_req1 = tsi.ScorerCreateReq(
            project_id=project_id,
            name="scorer_1",
            op_source_code="def score1():\n    return 1",
        )
        scorer_res1 = client.server.scorer_create(scorer_req1)

        scorer_req2 = tsi.ScorerCreateReq(
            project_id=project_id,
            name="scorer_2",
            op_source_code="def score2():\n    return 2",
        )
        scorer_res2 = client.server.scorer_create(scorer_req2)

        # Build refs
        entity, project = from_project_id(project_id)
        dataset_ref = f"weave:///{entity}/{project}/object/{dataset_res.object_id}:{dataset_res.digest}"
        scorer_ref1 = f"weave:///{entity}/{project}/object/{scorer_res1.object_id}:{scorer_res1.digest}"
        scorer_ref2 = f"weave:///{entity}/{project}/object/{scorer_res2.object_id}:{scorer_res2.digest}"

        # Create evaluation with scorers
        eval_req = tsi.EvaluationCreateReq(
            project_id=project_id,
            name="eval_with_scorers",
            dataset=dataset_ref,
            scorers=[scorer_ref1, scorer_ref2],
        )
        eval_res = client.server.evaluation_create(eval_req)

        # Read it back and verify scorers
        read_req = tsi.EvaluationReadReq(
            project_id=project_id,
            object_id=eval_res.object_id,
            digest=eval_res.digest,
        )
        read_res = client.server.evaluation_read(read_req)

        assert len(read_res.scorers) == 2
        assert scorer_ref1 in read_res.scorers
        assert scorer_ref2 in read_res.scorers


class TestV2APIIntegration:
    """Integration tests for V2 API endpoints."""

    def test_complete_evaluation_workflow(self, client):
        """Test a complete workflow: create dataset, scorers, and evaluation."""
        project_id = client._project_id()
        entity, project = from_project_id(project_id)

        # Step 1: Create a dataset
        dataset_req = tsi.DatasetCreateReq(
            project_id=project_id,
            name="workflow_dataset",
            description="Dataset for workflow test",
            rows=[
                {"question": "What is 2+2?", "answer": "4"},
                {"question": "What is 3+3?", "answer": "6"},
            ],
        )
        dataset_res = client.server.dataset_create(dataset_req)
        dataset_ref = f"weave:///{entity}/{project}/object/{dataset_res.object_id}:{dataset_res.digest}"

        # Step 2: Create scorers
        exact_match_req = tsi.ScorerCreateReq(
            project_id=project_id,
            name="exact_match",
            description="Checks for exact match",
            op_source_code="def score(output, answer):\n    return output == answer",
        )
        exact_match_res = client.server.scorer_create(exact_match_req)
        exact_match_ref = f"weave:///{entity}/{project}/object/{exact_match_res.object_id}:{exact_match_res.digest}"

        length_req = tsi.ScorerCreateReq(
            project_id=project_id,
            name="length_check",
            description="Checks answer length",
            op_source_code="def score(output):\n    return len(output)",
        )
        length_res = client.server.scorer_create(length_req)
        length_ref = f"weave:///{entity}/{project}/object/{length_res.object_id}:{length_res.digest}"

        # Step 3: Create evaluation
        eval_req = tsi.EvaluationCreateReq(
            project_id=project_id,
            name="math_evaluation",
            description="Evaluates math questions",
            dataset=dataset_ref,
            scorers=[exact_match_ref, length_ref],
            trials=3,
            evaluation_name="Math Quiz v1",
        )
        eval_res = client.server.evaluation_create(eval_req)

        # Step 4: Verify all components exist and are linked
        # Read evaluation
        eval_read_req = tsi.EvaluationReadReq(
            project_id=project_id,
            object_id=eval_res.object_id,
            digest=eval_res.digest,
        )
        eval_read_res = client.server.evaluation_read(eval_read_req)

        assert eval_read_res.name == "math_evaluation"
        assert eval_read_res.dataset == dataset_ref
        assert len(eval_read_res.scorers) == 2
        assert exact_match_ref in eval_read_res.scorers
        assert length_ref in eval_read_res.scorers
        assert eval_read_res.trials == 3
        assert eval_read_res.evaluation_name == "Math Quiz v1"

        # Verify we can read the dataset
        dataset_read_req = tsi.DatasetReadReq(
            project_id=project_id,
            object_id=dataset_res.object_id,
            digest=dataset_res.digest,
        )
        dataset_read_res = client.server.dataset_read(dataset_read_req)
        assert dataset_read_res.name == "workflow_dataset"

        # Verify we can read the scorers
        scorer1_read_req = tsi.ScorerReadReq(
            project_id=project_id,
            object_id=exact_match_res.object_id,
            digest=exact_match_res.digest,
        )
        scorer1_read_res = client.server.scorer_read(scorer1_read_req)
        assert scorer1_read_res.name == "exact_match"

        scorer2_read_req = tsi.ScorerReadReq(
            project_id=project_id,
            object_id=length_res.object_id,
            digest=length_res.digest,
        )
        scorer2_read_res = client.server.scorer_read(scorer2_read_req)
        assert scorer2_read_res.name == "length_check"

    def test_versioning_workflow(self, client):
        """Test that versioning works correctly across V2 API."""
        project_id = client._project_id()

        # Create multiple versions of the same op
        versions = []
        for i in range(3):
            req = tsi.OpCreateReq(
                project_id=project_id,
                name="versioned_op",
                source_code=f"def versioned():\n    return {i}",
            )
            res = client.server.op_create(req)
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
            read_req = tsi.OpReadReq(
                project_id=project_id,
                object_id="versioned_op",
                digest=version.digest,
            )
            read_res = client.server.op_read(read_req)
            assert read_res.digest == version.digest
            assert read_res.version_index == version.version_index


class TestModelsV2API:
    """Tests for Models V2 API endpoints."""

    def test_model_create(self, client):
        """Test creating a model via V2 API."""
        project_id = client._project_id()

        # Create a model
        req = tsi.ModelCreateReq(
            project_id=project_id,
            name="TestModel",
            description="A test model",
            source_code="""import weave

class TestModel(weave.Model):
    temperature: float = 0.7

    @weave.op
    def predict(self, input: str) -> dict:
        return {"output": f"Processed: {input}"}
""",
            attributes={"temperature": 0.7},
        )
        res = client.server.model_create(req)

        # Verify response
        assert res.object_id == "testmodel"
        assert res.digest is not None
        assert res.version_index == 0
        assert res.model_ref is not None

    def test_model_read(self, client):
        """Test reading a model via V2 API."""
        project_id = client._project_id()

        # Create a model first
        source_code = """import weave

class MyTestModel(weave.Model):
    prompt: str = "Hello"

    @weave.op
    def predict(self, input: str) -> str:
        return f"{self.prompt} {input}"
"""
        create_req = tsi.ModelCreateReq(
            project_id=project_id,
            name="ReadableModel",
            description="Model for testing reads",
            source_code=source_code,
            attributes={"prompt": "Hello"},
        )
        create_res = client.server.model_create(create_req)

        # Read the model
        read_req = tsi.ModelReadReq(
            project_id=project_id,
            object_id=create_res.object_id,
            digest=create_res.digest,
        )
        read_res = client.server.model_read(read_req)

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

    def test_model_list(self, client):
        """Test listing models via V2 API."""
        project_id = client._project_id()

        # Create multiple models
        for i in range(3):
            req = tsi.ModelCreateReq(
                project_id=project_id,
                name=f"ListTestModel{i}",
                source_code=f"""import weave

class ListTestModel{i}(weave.Model):
    @weave.op
    def predict(self):
        return {i}
""",
            )
            client.server.model_create(req)

        # List models
        list_req = tsi.ModelListReq(project_id=project_id)
        models = list(client.server.model_list(list_req))

        # Verify we get at least our 3 models
        assert len(models) >= 3
        model_names = [m.name for m in models]
        assert "ListTestModel0" in model_names
        assert "ListTestModel1" in model_names
        assert "ListTestModel2" in model_names

    def test_model_delete(self, client):
        """Test deleting a model via V2 API."""
        project_id = client._project_id()

        # Create a model
        create_req = tsi.ModelCreateReq(
            project_id=project_id,
            name="DeletableModel",
            source_code="""import weave

class DeletableModel(weave.Model):
    @weave.op
    def predict(self):
        pass
""",
        )
        create_res = client.server.model_create(create_req)

        # Delete the model
        delete_req = tsi.ModelDeleteReq(
            project_id=project_id,
            object_id=create_res.object_id,
            digests=[create_res.digest],
        )
        delete_res = client.server.model_delete(delete_req)

        # Verify deletion
        assert delete_res.num_deleted == 1

    def test_model_delete_all_versions(self, client):
        """Test deleting all versions of a model via V2 API."""
        project_id = client._project_id()

        # Create multiple versions
        digests = []
        for i in range(3):
            create_req = tsi.ModelCreateReq(
                project_id=project_id,
                name="MultiVersionModel",
                source_code=f"""import weave

class MultiVersionModel(weave.Model):
    version: int = {i}

    @weave.op
    def predict(self):
        return {i}
""",
            )
            create_res = client.server.model_create(create_req)
            digests.append(create_res.digest)

        # Delete all versions (None means delete all)
        delete_req = tsi.ModelDeleteReq(
            project_id=project_id,
            object_id="multiversionmodel",
            digests=None,
        )
        delete_res = client.server.model_delete(delete_req)

        # Verify all versions deleted
        assert delete_res.num_deleted == 3


class TestEvaluationRunsV2API:
    """Tests for Evaluation Runs V2 API endpoints."""

    def test_evaluation_run_create(self, client):
        """Test creating an evaluation run via V2 API."""
        project_id = client._project_id()
        entity, project = from_project_id(project_id)

        # Create dataset
        dataset_req = tsi.DatasetCreateReq(
            project_id=project_id,
            name="eval_run_dataset",
            rows=[{"input": "test", "output": "result"}],
        )
        dataset_res = client.server.dataset_create(dataset_req)
        dataset_ref = f"weave:///{entity}/{project}/object/{dataset_res.object_id}:{dataset_res.digest}"

        # Create evaluation
        eval_req = tsi.EvaluationCreateReq(
            project_id=project_id,
            name="eval_run_evaluation",
            dataset=dataset_ref,
            scorers=[],
        )
        eval_res = client.server.evaluation_create(eval_req)

        # Create model
        model_req = tsi.ModelCreateReq(
            project_id=project_id,
            name="EvalRunModel",
            source_code="""import weave

class EvalRunModel(weave.Model):
    @weave.op
    def predict(self, input: str) -> str:
        return "prediction"
""",
        )
        model_res = client.server.model_create(model_req)

        # Create evaluation run
        run_req = tsi.EvaluationRunCreateReq(
            project_id=project_id,
            evaluation=eval_res.evaluation_ref,
            model=model_res.model_ref,
        )
        run_res = client.server.evaluation_run_create(run_req)

        # Verify response
        assert run_res.evaluation_run_id is not None

    def test_evaluation_run_read(self, client):
        """Test reading an evaluation run via V2 API."""
        project_id = client._project_id()
        entity, project = from_project_id(project_id)

        # Create necessary components
        dataset_req = tsi.DatasetCreateReq(
            project_id=project_id,
            name="read_eval_run_dataset",
            rows=[{"x": 1}],
        )
        dataset_res = client.server.dataset_create(dataset_req)
        dataset_ref = f"weave:///{entity}/{project}/object/{dataset_res.object_id}:{dataset_res.digest}"

        eval_req = tsi.EvaluationCreateReq(
            project_id=project_id,
            name="read_eval_run_evaluation",
            dataset=dataset_ref,
            scorers=[],
        )
        eval_res = client.server.evaluation_create(eval_req)

        model_req = tsi.ModelCreateReq(
            project_id=project_id,
            name="ReadEvalRunModel",
            source_code="""import weave

class ReadEvalRunModel(weave.Model):
    @weave.op
    def predict(self, input):
        return "output"
""",
        )
        model_res = client.server.model_create(model_req)

        # Create evaluation run
        run_req = tsi.EvaluationRunCreateReq(
            project_id=project_id,
            evaluation=eval_res.evaluation_ref,
            model=model_res.model_ref,
        )
        run_res = client.server.evaluation_run_create(run_req)

        # Read the evaluation run
        read_req = tsi.EvaluationRunReadReq(
            project_id=project_id,
            evaluation_run_id=run_res.evaluation_run_id,
        )
        read_res = client.server.evaluation_run_read(read_req)

        # Verify response
        assert read_res.evaluation_run_id == run_res.evaluation_run_id
        assert read_res.evaluation == eval_res.evaluation_ref
        assert read_res.model == model_res.model_ref

    def test_evaluation_run_list(self, client):
        """Test listing evaluation runs via V2 API."""
        project_id = client._project_id()
        entity, project = from_project_id(project_id)

        # Create dataset
        dataset_req = tsi.DatasetCreateReq(
            project_id=project_id,
            name="list_eval_run_dataset",
            rows=[{"data": "value"}],
        )
        dataset_res = client.server.dataset_create(dataset_req)
        dataset_ref = f"weave:///{entity}/{project}/object/{dataset_res.object_id}:{dataset_res.digest}"

        # Create evaluation
        eval_req = tsi.EvaluationCreateReq(
            project_id=project_id,
            name="list_eval_run_evaluation",
            dataset=dataset_ref,
            scorers=[],
        )
        eval_res = client.server.evaluation_create(eval_req)

        # Create models and runs
        run_ids = []
        for i in range(3):
            model_req = tsi.ModelCreateReq(
                project_id=project_id,
                name=f"ListEvalRunModel{i}",
                source_code=f"""import weave

class ListEvalRunModel{i}(weave.Model):
    @weave.op
    def predict(self, input):
        return {i}
""",
            )
            model_res = client.server.model_create(model_req)

            run_req = tsi.EvaluationRunCreateReq(
                project_id=project_id,
                evaluation=eval_res.evaluation_ref,
                model=model_res.model_ref,
            )
            run_res = client.server.evaluation_run_create(run_req)
            run_ids.append(run_res.evaluation_run_id)

        # List evaluation runs
        list_req = tsi.EvaluationRunListReq(project_id=project_id)
        runs = list(client.server.evaluation_run_list(list_req))

        # Verify we get at least our 3 runs
        assert len(runs) >= 3
        returned_ids = [r.evaluation_run_id for r in runs]
        for run_id in run_ids:
            assert run_id in returned_ids

    def test_evaluation_run_delete(self, client):
        """Test deleting evaluation runs via V2 API."""
        project_id = client._project_id()
        entity, project = from_project_id(project_id)

        # Create dataset
        dataset_req = tsi.DatasetCreateReq(
            project_id=project_id,
            name="delete_eval_run_dataset",
            rows=[{"data": "test"}],
        )
        dataset_res = client.server.dataset_create(dataset_req)
        dataset_ref = f"weave:///{entity}/{project}/object/{dataset_res.object_id}:{dataset_res.digest}"

        # Create evaluation
        eval_req = tsi.EvaluationCreateReq(
            project_id=project_id,
            name="delete_eval_run_evaluation",
            dataset=dataset_ref,
            scorers=[],
        )
        eval_res = client.server.evaluation_create(eval_req)

        # Create model
        model_req = tsi.ModelCreateReq(
            project_id=project_id,
            name="DeleteEvalRunModel",
            source_code="""import weave

class DeleteEvalRunModel(weave.Model):
    @weave.op
    def predict(self, input):
        return "output"
""",
        )
        model_res = client.server.model_create(model_req)

        # Create evaluation run
        run_req = tsi.EvaluationRunCreateReq(
            project_id=project_id,
            evaluation=eval_res.evaluation_ref,
            model=model_res.model_ref,
        )
        run_res = client.server.evaluation_run_create(run_req)

        # Delete the evaluation run
        delete_req = tsi.EvaluationRunDeleteReq(
            project_id=project_id,
            evaluation_run_ids=[run_res.evaluation_run_id],
        )
        delete_res = client.server.evaluation_run_delete(delete_req)

        # Verify deletion
        assert delete_res.num_deleted == 1

    def test_evaluation_run_finish(self, client):
        """Test finishing an evaluation run via V2 API."""
        project_id = client._project_id()
        entity, project = from_project_id(project_id)

        # Create dataset
        dataset_req = tsi.DatasetCreateReq(
            project_id=project_id,
            name="finish_eval_run_dataset",
            rows=[{"data": "test"}],
        )
        dataset_res = client.server.dataset_create(dataset_req)
        dataset_ref = f"weave:///{entity}/{project}/object/{dataset_res.object_id}:{dataset_res.digest}"

        # Create evaluation
        eval_req = tsi.EvaluationCreateReq(
            project_id=project_id,
            name="finish_eval_run_evaluation",
            dataset=dataset_ref,
            scorers=[],
        )
        eval_res = client.server.evaluation_create(eval_req)

        # Create model
        model_req = tsi.ModelCreateReq(
            project_id=project_id,
            name="FinishEvalRunModel",
            source_code="""import weave

class FinishEvalRunModel(weave.Model):
    @weave.op
    def predict(self, input):
        return "output"
""",
        )
        model_res = client.server.model_create(model_req)

        # Create evaluation run
        run_req = tsi.EvaluationRunCreateReq(
            project_id=project_id,
            evaluation=eval_res.evaluation_ref,
            model=model_res.model_ref,
        )
        run_res = client.server.evaluation_run_create(run_req)

        # Finish the evaluation run
        finish_req = tsi.EvaluationRunFinishReq(
            project_id=project_id,
            evaluation_run_id=run_res.evaluation_run_id,
            summary={"accuracy": 0.95, "total": 100},
        )
        finish_res = client.server.evaluation_run_finish(finish_req)

        # Verify finish response
        assert finish_res.success is True


class TestPredictionsV2API:
    """Tests for Predictions V2 API endpoints."""

    def test_prediction_create(self, client):
        """Test creating a prediction via V2 API."""
        project_id = client._project_id()
        entity, project = from_project_id(project_id)

        # Create model
        model_req = tsi.ModelCreateReq(
            project_id=project_id,
            name="PredictionTestModel",
            source_code="""import weave

class PredictionTestModel(weave.Model):
    @weave.op
    def predict(self, input: str) -> str:
        return f"prediction for {input}"
""",
        )
        model_res = client.server.model_create(model_req)

        # Create prediction
        pred_req = tsi.PredictionCreateReq(
            project_id=project_id,
            model=model_res.model_ref,
            inputs={"input": "test query"},
            output="prediction for test query",
        )
        pred_res = client.server.prediction_create(pred_req)

        # Verify response
        assert pred_res.prediction_id is not None

    def test_prediction_read(self, client):
        """Test reading a prediction via V2 API."""
        project_id = client._project_id()
        entity, project = from_project_id(project_id)

        # Create model
        model_req = tsi.ModelCreateReq(
            project_id=project_id,
            name="ReadPredictionModel",
            source_code="""import weave

class ReadPredictionModel(weave.Model):
    @weave.op
    def predict(self, input: str) -> str:
        return "result"
""",
        )
        model_res = client.server.model_create(model_req)

        # Create prediction
        pred_req = tsi.PredictionCreateReq(
            project_id=project_id,
            model=model_res.model_ref,
            inputs={"question": "What is 2+2?"},
            output="4",
        )
        pred_res = client.server.prediction_create(pred_req)

        # Read the prediction
        read_req = tsi.PredictionReadReq(
            project_id=project_id,
            prediction_id=pred_res.prediction_id,
        )
        read_res = client.server.prediction_read(read_req)

        # Verify response
        assert read_res.prediction_id == pred_res.prediction_id
        assert read_res.model == model_res.model_ref
        assert read_res.inputs == {"question": "What is 2+2?"}
        assert read_res.output == "4"

    def test_prediction_list(self, client):
        """Test listing predictions via V2 API."""
        project_id = client._project_id()
        entity, project = from_project_id(project_id)

        # Create model
        model_req = tsi.ModelCreateReq(
            project_id=project_id,
            name="ListPredictionModel",
            source_code="""import weave

class ListPredictionModel(weave.Model):
    @weave.op
    def predict(self, input):
        return "output"
""",
        )
        model_res = client.server.model_create(model_req)

        # Create multiple predictions
        pred_ids = []
        for i in range(3):
            pred_req = tsi.PredictionCreateReq(
                project_id=project_id,
                model=model_res.model_ref,
                inputs={"value": i},
                output=f"result_{i}",
            )
            pred_res = client.server.prediction_create(pred_req)
            pred_ids.append(pred_res.prediction_id)

        # List predictions
        list_req = tsi.PredictionListReq(project_id=project_id)
        predictions = list(client.server.prediction_list(list_req))

        # Verify we get at least our 3 predictions
        assert len(predictions) >= 3
        returned_ids = [p.prediction_id for p in predictions]
        for pred_id in pred_ids:
            assert pred_id in returned_ids

    def test_prediction_delete(self, client):
        """Test deleting predictions via V2 API."""
        project_id = client._project_id()
        entity, project = from_project_id(project_id)

        # Create model
        model_req = tsi.ModelCreateReq(
            project_id=project_id,
            name="DeletePredictionModel",
            source_code="""import weave

class DeletePredictionModel(weave.Model):
    @weave.op
    def predict(self, input):
        return "output"
""",
        )
        model_res = client.server.model_create(model_req)

        # Create predictions
        pred_ids = []
        for i in range(2):
            pred_req = tsi.PredictionCreateReq(
                project_id=project_id,
                model=model_res.model_ref,
                inputs={"x": i},
                output=i * 2,
            )
            pred_res = client.server.prediction_create(pred_req)
            pred_ids.append(pred_res.prediction_id)

        # Delete the predictions
        delete_req = tsi.PredictionDeleteReq(
            project_id=project_id,
            prediction_ids=pred_ids,
        )
        delete_res = client.server.prediction_delete(delete_req)

        # Verify deletion
        assert delete_res.num_deleted == 2

    def test_prediction_with_evaluation_run(self, client):
        """Test creating a prediction linked to an evaluation run."""
        project_id = client._project_id()
        entity, project = from_project_id(project_id)

        # Create dataset
        dataset_req = tsi.DatasetCreateReq(
            project_id=project_id,
            name="pred_eval_run_dataset",
            rows=[{"input": "test"}],
        )
        dataset_res = client.server.dataset_create(dataset_req)
        dataset_ref = f"weave:///{entity}/{project}/object/{dataset_res.object_id}:{dataset_res.digest}"

        # Create evaluation
        eval_req = tsi.EvaluationCreateReq(
            project_id=project_id,
            name="pred_eval_run_evaluation",
            dataset=dataset_ref,
            scorers=[],
        )
        eval_res = client.server.evaluation_create(eval_req)

        # Create model
        model_req = tsi.ModelCreateReq(
            project_id=project_id,
            name="PredEvalRunModel",
            source_code="""import weave

class PredEvalRunModel(weave.Model):
    @weave.op
    def predict(self, input):
        return "output"
""",
        )
        model_res = client.server.model_create(model_req)

        # Create evaluation run
        run_req = tsi.EvaluationRunCreateReq(
            project_id=project_id,
            evaluation=eval_res.evaluation_ref,
            model=model_res.model_ref,
        )
        run_res = client.server.evaluation_run_create(run_req)

        # Create prediction linked to evaluation run
        pred_req = tsi.PredictionCreateReq(
            project_id=project_id,
            model=model_res.model_ref,
            inputs={"input": "test"},
            output="result",
            evaluation_run_id=run_res.evaluation_run_id,
        )
        pred_res = client.server.prediction_create(pred_req)

        # Read and verify the link
        read_req = tsi.PredictionReadReq(
            project_id=project_id,
            prediction_id=pred_res.prediction_id,
        )
        read_res = client.server.prediction_read(read_req)

        assert read_res.evaluation_run_id == run_res.evaluation_run_id

        # Finish the prediction (which should end the predict_and_score call with model_latency)
        finish_req = tsi.PredictionFinishReq(
            project_id=project_id,
            prediction_id=pred_res.prediction_id,
        )
        finish_res = client.server.prediction_finish(finish_req)
        assert finish_res.success is True

        # Verify the predict_and_score call has model_latency in its output
        prediction_call_req = tsi.CallReadReq(
            project_id=project_id,
            id=pred_res.prediction_id,
        )
        prediction_call_res = client.server.call_read(prediction_call_req)
        assert prediction_call_res.call is not None
        assert prediction_call_res.call.parent_id is not None

        # Read the predict_and_score call (parent of prediction)
        predict_and_score_req = tsi.CallReadReq(
            project_id=project_id,
            id=prediction_call_res.call.parent_id,
        )
        predict_and_score_res = client.server.call_read(predict_and_score_req)
        assert predict_and_score_res.call is not None
        assert predict_and_score_res.call.output is not None
        assert "model_latency" in predict_and_score_res.call.output
        assert isinstance(predict_and_score_res.call.output["model_latency"], dict)
        assert "mean" in predict_and_score_res.call.output["model_latency"]
        assert isinstance(
            predict_and_score_res.call.output["model_latency"]["mean"], (int, float)
        )
        assert predict_and_score_res.call.output["model_latency"]["mean"] >= 0
        assert "output" in predict_and_score_res.call.output
        assert predict_and_score_res.call.output["output"] == "result"


class TestScoresV2API:
    """Tests for Scores V2 API endpoints."""

    def test_score_create(self, client):
        """Test creating a score via V2 API."""
        project_id = client._project_id()
        entity, project = from_project_id(project_id)

        # Create scorer
        scorer_req = tsi.ScorerCreateReq(
            project_id=project_id,
            name="score_test_scorer",
            op_source_code="def score(output, target):\n    return 1.0",
        )
        scorer_res = client.server.scorer_create(scorer_req)
        scorer_ref = f"weave:///{entity}/{project}/object/{scorer_res.object_id}:{scorer_res.digest}"

        # Create model
        model_req = tsi.ModelCreateReq(
            project_id=project_id,
            name="ScoreTestModel",
            source_code="""import weave

class ScoreTestModel(weave.Model):
    @weave.op
    def predict(self, input):
        return "output"
""",
        )
        model_res = client.server.model_create(model_req)

        # Create prediction
        pred_req = tsi.PredictionCreateReq(
            project_id=project_id,
            model=model_res.model_ref,
            inputs={"input": "test"},
            output="result",
        )
        pred_res = client.server.prediction_create(pred_req)

        # Create score
        score_req = tsi.ScoreCreateReq(
            project_id=project_id,
            prediction_id=pred_res.prediction_id,
            scorer=scorer_ref,
            value=0.95,
        )
        score_res = client.server.score_create(score_req)

        # Verify response
        assert score_res.score_id is not None

    def test_score_read(self, client):
        """Test reading a score via V2 API."""
        project_id = client._project_id()
        entity, project = from_project_id(project_id)

        # Create scorer
        scorer_req = tsi.ScorerCreateReq(
            project_id=project_id,
            name="read_score_scorer",
            op_source_code="def score(output):\n    return len(output)",
        )
        scorer_res = client.server.scorer_create(scorer_req)
        scorer_ref = f"weave:///{entity}/{project}/object/{scorer_res.object_id}:{scorer_res.digest}"

        # Create model
        model_req = tsi.ModelCreateReq(
            project_id=project_id,
            name="ReadScoreModel",
            source_code="""import weave

class ReadScoreModel(weave.Model):
    @weave.op
    def predict(self, input):
        return "output"
""",
        )
        model_res = client.server.model_create(model_req)

        # Create prediction
        pred_req = tsi.PredictionCreateReq(
            project_id=project_id,
            model=model_res.model_ref,
            inputs={"input": "question"},
            output="answer",
        )
        pred_res = client.server.prediction_create(pred_req)

        # Create score
        score_req = tsi.ScoreCreateReq(
            project_id=project_id,
            prediction_id=pred_res.prediction_id,
            scorer=scorer_ref,
            value=0.85,
        )
        score_res = client.server.score_create(score_req)

        # Read the score
        read_req = tsi.ScoreReadReq(
            project_id=project_id,
            score_id=score_res.score_id,
        )
        read_res = client.server.score_read(read_req)

        # Verify response
        assert read_res.score_id == score_res.score_id
        assert read_res.scorer == scorer_ref
        assert read_res.value == 0.85

    def test_score_list(self, client):
        """Test listing scores via V2 API."""
        project_id = client._project_id()
        entity, project = from_project_id(project_id)

        # Create scorer
        scorer_req = tsi.ScorerCreateReq(
            project_id=project_id,
            name="list_score_scorer",
            op_source_code="def score(output):\n    return 1.0",
        )
        scorer_res = client.server.scorer_create(scorer_req)
        scorer_ref = f"weave:///{entity}/{project}/object/{scorer_res.object_id}:{scorer_res.digest}"

        # Create model
        model_req = tsi.ModelCreateReq(
            project_id=project_id,
            name="ListScoreModel",
            source_code="""import weave

class ListScoreModel(weave.Model):
    @weave.op
    def predict(self, input):
        return "output"
""",
        )
        model_res = client.server.model_create(model_req)

        # Create predictions and scores
        score_ids = []
        for i in range(3):
            pred_req = tsi.PredictionCreateReq(
                project_id=project_id,
                model=model_res.model_ref,
                inputs={"value": i},
                output=f"result_{i}",
            )
            pred_res = client.server.prediction_create(pred_req)

            score_req = tsi.ScoreCreateReq(
                project_id=project_id,
                prediction_id=pred_res.prediction_id,
                scorer=scorer_ref,
                value=float(i) / 10,
            )
            score_res = client.server.score_create(score_req)
            score_ids.append(score_res.score_id)

        # List scores
        list_req = tsi.ScoreListReq(project_id=project_id)
        scores = list(client.server.score_list(list_req))

        # Verify we get at least our 3 scores
        assert len(scores) >= 3
        returned_ids = [s.score_id for s in scores]
        for score_id in score_ids:
            assert score_id in returned_ids

    def test_score_delete(self, client):
        """Test deleting scores via V2 API."""
        project_id = client._project_id()
        entity, project = from_project_id(project_id)

        # Create scorer
        scorer_req = tsi.ScorerCreateReq(
            project_id=project_id,
            name="delete_score_scorer",
            op_source_code="def score(output):\n    return 1.0",
        )
        scorer_res = client.server.scorer_create(scorer_req)
        scorer_ref = f"weave:///{entity}/{project}/object/{scorer_res.object_id}:{scorer_res.digest}"

        # Create model
        model_req = tsi.ModelCreateReq(
            project_id=project_id,
            name="DeleteScoreModel",
            source_code="""import weave

class DeleteScoreModel(weave.Model):
    @weave.op
    def predict(self, input):
        return "output"
""",
        )
        model_res = client.server.model_create(model_req)

        # Create predictions and scores
        score_ids = []
        for i in range(2):
            pred_req = tsi.PredictionCreateReq(
                project_id=project_id,
                model=model_res.model_ref,
                inputs={"x": i},
                output=i * 2,
            )
            pred_res = client.server.prediction_create(pred_req)

            score_req = tsi.ScoreCreateReq(
                project_id=project_id,
                prediction_id=pred_res.prediction_id,
                scorer=scorer_ref,
                value=0.5 * i,
            )
            score_res = client.server.score_create(score_req)
            score_ids.append(score_res.score_id)

        # Delete the scores
        delete_req = tsi.ScoreDeleteReq(
            project_id=project_id,
            score_ids=score_ids,
        )
        delete_res = client.server.score_delete(delete_req)

        # Verify deletion
        assert delete_res.num_deleted == 2

    def test_score_with_evaluation_run(self, client):
        """Test creating a score linked to an evaluation run."""
        project_id = client._project_id()
        entity, project = from_project_id(project_id)

        # Create dataset
        dataset_req = tsi.DatasetCreateReq(
            project_id=project_id,
            name="score_eval_run_dataset",
            rows=[{"input": "test"}],
        )
        dataset_res = client.server.dataset_create(dataset_req)
        dataset_ref = f"weave:///{entity}/{project}/object/{dataset_res.object_id}:{dataset_res.digest}"

        # Create scorer
        scorer_req = tsi.ScorerCreateReq(
            project_id=project_id,
            name="eval_run_scorer",
            op_source_code="def score(output):\n    return 1.0",
        )
        scorer_res = client.server.scorer_create(scorer_req)
        scorer_ref = f"weave:///{entity}/{project}/object/{scorer_res.object_id}:{scorer_res.digest}"

        # Create evaluation
        eval_req = tsi.EvaluationCreateReq(
            project_id=project_id,
            name="score_eval_run_evaluation",
            dataset=dataset_ref,
            scorers=[scorer_ref],
        )
        eval_res = client.server.evaluation_create(eval_req)

        # Create model
        model_req = tsi.ModelCreateReq(
            project_id=project_id,
            name="ScoreEvalRunModel",
            source_code="""import weave

class ScoreEvalRunModel(weave.Model):
    @weave.op
    def predict(self, input):
        return "output"
""",
        )
        model_res = client.server.model_create(model_req)

        # Create evaluation run
        run_req = tsi.EvaluationRunCreateReq(
            project_id=project_id,
            evaluation=eval_res.evaluation_ref,
            model=model_res.model_ref,
        )
        run_res = client.server.evaluation_run_create(run_req)

        # Create prediction
        pred_req = tsi.PredictionCreateReq(
            project_id=project_id,
            model=model_res.model_ref,
            inputs={"input": "test"},
            output="result",
            evaluation_run_id=run_res.evaluation_run_id,
        )
        pred_res = client.server.prediction_create(pred_req)

        # Create score linked to evaluation run
        score_req = tsi.ScoreCreateReq(
            project_id=project_id,
            prediction_id=pred_res.prediction_id,
            scorer=scorer_ref,
            value=0.9,
            evaluation_run_id=run_res.evaluation_run_id,
        )
        score_res = client.server.score_create(score_req)

        # Read and verify the link
        read_req = tsi.ScoreReadReq(
            project_id=project_id,
            score_id=score_res.score_id,
        )
        read_res = client.server.score_read(read_req)

        assert read_res.evaluation_run_id == run_res.evaluation_run_id


class TestEvalResultsReadAPI:
    """Tests for the read-oriented eval results API."""

    def test_eval_results_query_intersection(self, client):
        """Keeps only rows shared by all requested evaluations."""
        project_id = client._project_id()
        entity, project = from_project_id(project_id)

        scorer_res = client.server.scorer_create(
            tsi.ScorerCreateReq(
                project_id=project_id,
                name="intersection_scorer",
                op_source_code="def score(output):\n    return 1",
            )
        )
        scorer_ref = f"weave:///{entity}/{project}/object/{scorer_res.object_id}:{scorer_res.digest}"

        run_a = client.server.evaluation_run_create(
            tsi.EvaluationRunCreateReq(
                project_id=project_id,
                evaluation="eval://a",
                model="model://a",
            )
        )
        run_b = client.server.evaluation_run_create(
            tsi.EvaluationRunCreateReq(
                project_id=project_id,
                evaluation="eval://b",
                model="model://b",
            )
        )

        pred_a_shared = client.server.prediction_create(
            tsi.PredictionCreateReq(
                project_id=project_id,
                model="model://a",
                inputs={"x": "shared"},
                output="a-shared",
                evaluation_run_id=run_a.evaluation_run_id,
            )
        )
        pred_a_only = client.server.prediction_create(
            tsi.PredictionCreateReq(
                project_id=project_id,
                model="model://a",
                inputs={"x": "only-a"},
                output="a-only",
                evaluation_run_id=run_a.evaluation_run_id,
            )
        )
        pred_b_shared = client.server.prediction_create(
            tsi.PredictionCreateReq(
                project_id=project_id,
                model="model://b",
                inputs={"x": "shared"},
                output="b-shared",
                evaluation_run_id=run_b.evaluation_run_id,
            )
        )

        client.server.score_create(
            tsi.ScoreCreateReq(
                project_id=project_id,
                prediction_id=pred_a_shared.prediction_id,
                scorer=scorer_ref,
                value=0.5,
                evaluation_run_id=run_a.evaluation_run_id,
            )
        )
        client.server.score_create(
            tsi.ScoreCreateReq(
                project_id=project_id,
                prediction_id=pred_a_only.prediction_id,
                scorer=scorer_ref,
                value=0.2,
                evaluation_run_id=run_a.evaluation_run_id,
            )
        )
        client.server.score_create(
            tsi.ScoreCreateReq(
                project_id=project_id,
                prediction_id=pred_b_shared.prediction_id,
                scorer=scorer_ref,
                value=0.8,
                evaluation_run_id=run_b.evaluation_run_id,
            )
        )

        client.server.prediction_finish(
            tsi.PredictionFinishReq(
                project_id=project_id,
                prediction_id=pred_a_shared.prediction_id,
            )
        )
        client.server.prediction_finish(
            tsi.PredictionFinishReq(
                project_id=project_id,
                prediction_id=pred_a_only.prediction_id,
            )
        )
        client.server.prediction_finish(
            tsi.PredictionFinishReq(
                project_id=project_id,
                prediction_id=pred_b_shared.prediction_id,
            )
        )

        res = client.server.eval_results_query(
            tsi.EvalResultsQueryReq(
                project_id=project_id,
                evaluation_call_ids=[run_a.evaluation_run_id, run_b.evaluation_run_id],
                require_intersection=True,
            )
        )

        assert res.total_rows == 1
        assert len(res.rows) == 1
        assert {e.evaluation_call_id for e in res.rows[0].evaluations} == {
            run_a.evaluation_run_id,
            run_b.evaluation_run_id,
        }

    def test_eval_results_summary_pass_signal(self, client):
        """Aggregates pass-rate stats from scorer outputs with `passed` booleans."""
        project_id = client._project_id()
        entity, project = from_project_id(project_id)

        scorer_res = client.server.scorer_create(
            tsi.ScorerCreateReq(
                project_id=project_id,
                name="pass_scorer",
                op_source_code="def score(output):\n    return 1",
            )
        )
        scorer_ref = f"weave:///{entity}/{project}/object/{scorer_res.object_id}:{scorer_res.digest}"

        run = client.server.evaluation_run_create(
            tsi.EvaluationRunCreateReq(
                project_id=project_id,
                evaluation="eval://pass",
                model="model://pass",
            )
        )
        prediction = client.server.prediction_create(
            tsi.PredictionCreateReq(
                project_id=project_id,
                model="model://pass",
                inputs={"x": "pass-data"},
                output="output",
                evaluation_run_id=run.evaluation_run_id,
            )
        )

        prediction_call = client.server.call_read(
            tsi.CallReadReq(project_id=project_id, id=prediction.prediction_id)
        ).call
        assert prediction_call is not None
        assert prediction_call.parent_id is not None
        predict_and_score_id = prediction_call.parent_id

        score_call_id = generate_id()
        client.server.call_start(
            tsi.CallStartReq(
                start=tsi.StartedCallSchemaForInsert(
                    project_id=project_id,
                    id=score_call_id,
                    trace_id=run.evaluation_run_id,
                    parent_id=predict_and_score_id,
                    op_name="PassScorer.score",
                    started_at=datetime.datetime.now(datetime.timezone.utc),
                    attributes={
                        constants.WEAVE_ATTRIBUTES_NAMESPACE: {
                            constants.SCORE_ATTR_KEY: "true",
                            constants.SCORE_SCORER_ATTR_KEY: scorer_ref,
                        }
                    },
                    inputs={"self": scorer_ref},
                    wb_user_id="test-user",
                )
            )
        )
        client.server.call_end(
            tsi.CallEndReq(
                end=tsi.EndedCallSchemaForInsert(
                    project_id=project_id,
                    id=score_call_id,
                    ended_at=datetime.datetime.now(datetime.timezone.utc),
                    output={"passed": True},
                    summary={},
                )
            )
        )
        client.server.prediction_finish(
            tsi.PredictionFinishReq(
                project_id=project_id, prediction_id=prediction.prediction_id
            )
        )

        summary = client.server.eval_results_query(
            tsi.EvalResultsQueryReq(
                project_id=project_id,
                evaluation_call_ids=[run.evaluation_run_id],
                require_intersection=False,
                include_rows=False,
                include_summary=True,
            )
        ).summary

        eval_summary = next(
            e
            for e in summary.evaluations
            if e.evaluation_call_id == run.evaluation_run_id
        )
        scorer_stats = next(
            s
            for s in eval_summary.scorer_stats
            if s.scorer_key == "pass_scorer" and s.path == "passed"
        )
        assert eval_summary.trial_count == 1
        assert scorer_stats.path == "passed"
        assert scorer_stats.value_type == "binary"
        assert scorer_stats.pass_known_count == 1
        assert scorer_stats.pass_true_count == 1
        assert scorer_stats.pass_rate == 1.0

    def test_eval_results_summary_nested_passed_dimension(self, client):
        """Verify scorer_stats emits one entry per flattened leaf (e.g. token_distance.passed)."""
        project_id = client._project_id()
        entity, project = from_project_id(project_id)

        scorer_res = client.server.scorer_create(
            tsi.ScorerCreateReq(
                project_id=project_id,
                name="token_distance",
                op_source_code="def score(output):\n    return 0",
            )
        )
        scorer_ref = f"weave:///{entity}/{project}/object/{scorer_res.object_id}:{scorer_res.digest}"

        run = client.server.evaluation_run_create(
            tsi.EvaluationRunCreateReq(
                project_id=project_id,
                evaluation="eval://token",
                model="model://token",
            )
        )
        prediction = client.server.prediction_create(
            tsi.PredictionCreateReq(
                project_id=project_id,
                model="model://token",
                inputs={"x": "data"},
                output="output",
                evaluation_run_id=run.evaluation_run_id,
            )
        )
        prediction_call = client.server.call_read(
            tsi.CallReadReq(project_id=project_id, id=prediction.prediction_id)
        ).call
        assert prediction_call is not None
        assert prediction_call.parent_id is not None

        score_call_id = generate_id()
        client.server.call_start(
            tsi.CallStartReq(
                start=tsi.StartedCallSchemaForInsert(
                    project_id=project_id,
                    id=score_call_id,
                    trace_id=run.evaluation_run_id,
                    parent_id=prediction_call.parent_id,
                    op_name="TokenDistance.score",
                    started_at=datetime.datetime.now(datetime.timezone.utc),
                    attributes={
                        constants.WEAVE_ATTRIBUTES_NAMESPACE: {
                            constants.SCORE_ATTR_KEY: "true",
                            constants.SCORE_SCORER_ATTR_KEY: scorer_ref,
                        }
                    },
                    inputs={"self": scorer_ref},
                    wb_user_id="test-user",
                )
            )
        )
        client.server.call_end(
            tsi.CallEndReq(
                end=tsi.EndedCallSchemaForInsert(
                    project_id=project_id,
                    id=score_call_id,
                    ended_at=datetime.datetime.now(datetime.timezone.utc),
                    output={"passed": True, "distance_tokens": 0},
                    summary={},
                )
            )
        )
        client.server.prediction_finish(
            tsi.PredictionFinishReq(
                project_id=project_id, prediction_id=prediction.prediction_id
            )
        )

        summary = client.server.eval_results_query(
            tsi.EvalResultsQueryReq(
                project_id=project_id,
                evaluation_call_ids=[run.evaluation_run_id],
                require_intersection=False,
                include_rows=False,
                include_summary=True,
            )
        ).summary

        eval_summary = next(
            e
            for e in summary.evaluations
            if e.evaluation_call_id == run.evaluation_run_id
        )
        assert eval_summary.trial_count == 1
        assert len(eval_summary.scorer_stats) == 2

        passed_stats = next(
            s
            for s in eval_summary.scorer_stats
            if s.scorer_key == "token_distance" and s.path == "passed"
        )
        assert passed_stats.value_type == "binary"
        assert passed_stats.pass_known_count == 1
        assert passed_stats.pass_true_count == 1
        assert passed_stats.pass_rate == 1.0

        distance_stats = next(
            s
            for s in eval_summary.scorer_stats
            if s.scorer_key == "token_distance" and s.path == "distance_tokens"
        )
        assert distance_stats.value_type == "continuous"
        assert distance_stats.numeric_count == 1
        assert distance_stats.numeric_mean == 0.0

    def test_eval_results_from_high_level_evaluation(self, client):
        """Run a real weave.Evaluation then verify eval_results_query and summary."""
        project_id = client._project_id()

        class MatchScorer(weave.Scorer):
            @weave.op
            def score(self, target, output):
                return {"passed": target == output}

        @weave.op
        def length_scorer(target, output) -> float:
            return abs(len(str(output)) - len(str(target)))

        @weave.op
        async def predict(input) -> str:
            return str(eval(input))

        dataset_rows = [
            {"input": "1 + 2", "target": "3"},
            {"input": "2 ** 4", "target": "16"},
        ]

        evaluation = weave.Evaluation(
            name="high-level-test",
            dataset=dataset_rows,
            scorers=[MatchScorer(), length_scorer],
        )
        asyncio.run(evaluation.evaluate(predict))
        client.flush()

        all_calls = list(
            client.server.calls_query_stream(
                tsi.CallsQueryReq(
                    project_id=project_id,
                    columns=["id", "op_name"],
                )
            )
        )
        eval_root_id = next(
            c.id for c in all_calls if c.op_name and "Evaluation.evaluate" in c.op_name
        )

        res = client.server.eval_results_query(
            tsi.EvalResultsQueryReq(
                project_id=project_id,
                evaluation_call_ids=[eval_root_id],
            )
        )

        assert res.total_rows == 2
        for row in res.rows:
            assert len(row.evaluations) == 1
            eval_entry = row.evaluations[0]
            assert eval_entry.evaluation_call_id == eval_root_id
            assert len(eval_entry.trials) == 1
            trial = eval_entry.trials[0]
            assert trial.model_output is not None
            assert trial.predict_call_id is not None
            assert "MatchScorer" in trial.scores
            assert "length_scorer" in trial.scores

        summary = client.server.eval_results_query(
            tsi.EvalResultsQueryReq(
                project_id=project_id,
                evaluation_call_ids=[eval_root_id],
                require_intersection=False,
                include_rows=False,
                include_summary=True,
            )
        ).summary
        assert summary.row_count == 2
        eval_sum = next(
            e for e in summary.evaluations if e.evaluation_call_id == eval_root_id
        )
        assert eval_sum.trial_count == 2
        stats_by_key_path = {(s.scorer_key, s.path): s for s in eval_sum.scorer_stats}
        match_stats = stats_by_key_path.get(("MatchScorer", "passed"))
        assert match_stats is not None
        assert match_stats.pass_known_count == 2
        assert match_stats.pass_true_count == 2
        assert match_stats.pass_rate == 1.0

    def test_eval_results_from_imperative_evaluation(self, client):
        """Run a real EvaluationLogger then verify eval_results_query and summary."""
        project_id = client._project_id()

        ev = EvaluationLogger()

        pred1 = ev.log_prediction(inputs={"q": "hello"}, output="world")
        pred1.log_score(scorer="accuracy", score=True)
        pred1.log_score(scorer="confidence", score=0.9)
        pred1.finish()

        pred2 = ev.log_prediction(inputs={"q": "foo"}, output="bar")
        pred2.log_score(scorer="accuracy", score=False)
        pred2.log_score(scorer="confidence", score=0.3)
        pred2.finish()

        pred3 = ev.log_prediction(inputs={"q": "baz"}, output="qux")
        pred3.log_score(scorer="accuracy", score=True)
        pred3.log_score(scorer="confidence", score=0.7)
        pred3.finish()

        ev.log_summary({"accuracy_mean": 0.67})
        client.flush()

        eval_root_id = ev._evaluate_call.id

        res = client.server.eval_results_query(
            tsi.EvalResultsQueryReq(
                project_id=project_id,
                evaluation_call_ids=[eval_root_id],
            )
        )

        assert res.total_rows == 3
        for row in res.rows:
            assert len(row.evaluations) == 1
            eval_entry = row.evaluations[0]
            assert eval_entry.evaluation_call_id == eval_root_id
            assert len(eval_entry.trials) == 1
            trial = eval_entry.trials[0]
            assert trial.model_output is not None
            assert "accuracy" in trial.scores
            assert "confidence" in trial.scores

        summary = client.server.eval_results_query(
            tsi.EvalResultsQueryReq(
                project_id=project_id,
                evaluation_call_ids=[eval_root_id],
                require_intersection=False,
                include_rows=False,
                include_summary=True,
            )
        ).summary
        assert summary.row_count == 3
        eval_sum = next(
            e for e in summary.evaluations if e.evaluation_call_id == eval_root_id
        )
        assert eval_sum.trial_count == 3
        stats_by_key_path = {(s.scorer_key, s.path): s for s in eval_sum.scorer_stats}
        acc = stats_by_key_path.get(("accuracy", None))
        assert acc is not None
        assert acc.pass_known_count == 3
        assert acc.pass_true_count == 2
        assert acc.pass_rate == pytest.approx(2 / 3)

        conf = stats_by_key_path.get(("confidence", None))
        assert conf is not None
        assert conf.numeric_count == 3
        assert conf.numeric_mean == pytest.approx((0.9 + 0.3 + 0.7) / 3)
        assert conf.pass_known_count == 0

    def test_eval_results_summary_numeric_mean(self, client):
        """Verify numeric aggregation in eval_results_summary."""
        project_id = client._project_id()
        entity, project = from_project_id(project_id)

        scorer_res = client.server.scorer_create(
            tsi.ScorerCreateReq(
                project_id=project_id,
                name="numeric_scorer",
                op_source_code="def score(output):\n    return 1.0",
            )
        )
        scorer_ref = f"weave:///{entity}/{project}/object/{scorer_res.object_id}:{scorer_res.digest}"

        run = client.server.evaluation_run_create(
            tsi.EvaluationRunCreateReq(
                project_id=project_id,
                evaluation="eval://numeric",
                model="model://numeric",
            )
        )

        score_values = [0.5, 0.8, 0.2]
        for i, val in enumerate(score_values):
            pred = client.server.prediction_create(
                tsi.PredictionCreateReq(
                    project_id=project_id,
                    model="model://numeric",
                    inputs={"row_id": i},
                    output=f"output-{i}",
                    evaluation_run_id=run.evaluation_run_id,
                )
            )
            client.server.score_create(
                tsi.ScoreCreateReq(
                    project_id=project_id,
                    prediction_id=pred.prediction_id,
                    scorer=scorer_ref,
                    value=val,
                    evaluation_run_id=run.evaluation_run_id,
                )
            )
            client.server.prediction_finish(
                tsi.PredictionFinishReq(
                    project_id=project_id,
                    prediction_id=pred.prediction_id,
                )
            )

        summary = client.server.eval_results_query(
            tsi.EvalResultsQueryReq(
                project_id=project_id,
                evaluation_call_ids=[run.evaluation_run_id],
                require_intersection=False,
                include_rows=False,
                include_summary=True,
            )
        ).summary

        eval_sum = next(
            e
            for e in summary.evaluations
            if e.evaluation_call_id == run.evaluation_run_id
        )
        assert eval_sum.trial_count == 3
        stats = next(
            s
            for s in eval_sum.scorer_stats
            if s.scorer_key == "numeric_scorer" and s.path is None
        )
        assert stats.numeric_count == 3
        assert stats.numeric_mean == pytest.approx(0.5, abs=1e-9)
        assert stats.pass_rate is None
        assert stats.pass_known_count == 0

    def test_eval_results_query_multiple_scorers(self, client):
        """Verify multiple scorers appear in query and summary results."""
        project_id = client._project_id()
        entity, project = from_project_id(project_id)

        scorer_a_res = client.server.scorer_create(
            tsi.ScorerCreateReq(
                project_id=project_id,
                name="scorer_alpha",
                op_source_code="def score(output):\n    return True",
            )
        )
        scorer_a_ref = f"weave:///{entity}/{project}/object/{scorer_a_res.object_id}:{scorer_a_res.digest}"
        scorer_b_res = client.server.scorer_create(
            tsi.ScorerCreateReq(
                project_id=project_id,
                name="scorer_beta",
                op_source_code="def score(output):\n    return 0.5",
            )
        )
        scorer_b_ref = f"weave:///{entity}/{project}/object/{scorer_b_res.object_id}:{scorer_b_res.digest}"

        run = client.server.evaluation_run_create(
            tsi.EvaluationRunCreateReq(
                project_id=project_id,
                evaluation="eval://multi",
                model="model://multi",
            )
        )

        for i in range(2):
            pred = client.server.prediction_create(
                tsi.PredictionCreateReq(
                    project_id=project_id,
                    model="model://multi",
                    inputs={"row_id": i},
                    output=f"out-{i}",
                    evaluation_run_id=run.evaluation_run_id,
                )
            )
            prediction_call = client.server.call_read(
                tsi.CallReadReq(project_id=project_id, id=pred.prediction_id)
            ).call
            assert prediction_call is not None
            assert prediction_call.parent_id is not None
            pas_id = prediction_call.parent_id

            score_a_id = generate_id()
            client.server.call_start(
                tsi.CallStartReq(
                    start=tsi.StartedCallSchemaForInsert(
                        project_id=project_id,
                        id=score_a_id,
                        trace_id=run.evaluation_run_id,
                        parent_id=pas_id,
                        op_name="ScorerAlpha.score",
                        started_at=datetime.datetime.now(datetime.timezone.utc),
                        attributes={
                            constants.WEAVE_ATTRIBUTES_NAMESPACE: {
                                constants.SCORE_ATTR_KEY: "true",
                                constants.SCORE_SCORER_ATTR_KEY: scorer_a_ref,
                            }
                        },
                        inputs={"self": scorer_a_ref},
                        wb_user_id="test-user",
                    )
                )
            )
            client.server.call_end(
                tsi.CallEndReq(
                    end=tsi.EndedCallSchemaForInsert(
                        project_id=project_id,
                        id=score_a_id,
                        ended_at=datetime.datetime.now(datetime.timezone.utc),
                        output={"passed": i == 0},
                        summary={},
                    )
                )
            )

            client.server.score_create(
                tsi.ScoreCreateReq(
                    project_id=project_id,
                    prediction_id=pred.prediction_id,
                    scorer=scorer_b_ref,
                    value=0.1 * (i + 1),
                    evaluation_run_id=run.evaluation_run_id,
                )
            )
            client.server.prediction_finish(
                tsi.PredictionFinishReq(
                    project_id=project_id,
                    prediction_id=pred.prediction_id,
                )
            )

        res = client.server.eval_results_query(
            tsi.EvalResultsQueryReq(
                project_id=project_id,
                evaluation_call_ids=[run.evaluation_run_id],
            )
        )
        assert res.total_rows == 2
        for row in res.rows:
            trial = row.evaluations[0].trials[0]
            assert "scorer_alpha" in trial.scores
            assert "scorer_beta" in trial.scores

        summary = client.server.eval_results_query(
            tsi.EvalResultsQueryReq(
                project_id=project_id,
                evaluation_call_ids=[run.evaluation_run_id],
                require_intersection=False,
                include_rows=False,
                include_summary=True,
            )
        ).summary
        eval_sum = next(
            e
            for e in summary.evaluations
            if e.evaluation_call_id == run.evaluation_run_id
        )
        stats_by_key_path = {(s.scorer_key, s.path): s for s in eval_sum.scorer_stats}
        alpha = stats_by_key_path.get(("scorer_alpha", "passed"))
        assert alpha is not None
        assert alpha.pass_known_count == 2
        assert alpha.pass_true_count == 1
        assert alpha.pass_rate == pytest.approx(0.5)

        beta = stats_by_key_path.get(("scorer_beta", None))
        assert beta is not None
        assert beta.numeric_count == 2
        assert beta.numeric_mean == pytest.approx(0.15)

    def test_eval_results_query_combined_sections_match_separate_calls(self, client):
        """Combined eval_results/query sections should match separate query+summary."""
        project_id = client._project_id()
        ev = EvaluationLogger()

        pred1 = ev.log_prediction(inputs={"q": "hello"}, output="world")
        pred1.log_score(scorer="accuracy", score=True)
        pred1.log_score(scorer="confidence", score=0.9)
        pred1.finish()

        pred2 = ev.log_prediction(inputs={"q": "foo"}, output="bar")
        pred2.log_score(scorer="accuracy", score=False)
        pred2.log_score(scorer="confidence", score=0.3)
        pred2.finish()

        client.flush()
        eval_root_id = ev._evaluate_call.id

        separate_query = client.server.eval_results_query(
            tsi.EvalResultsQueryReq(
                project_id=project_id,
                evaluation_call_ids=[eval_root_id],
                require_intersection=True,
                include_raw_data_rows=True,
                resolve_row_refs=True,
            )
        )
        separate_summary = client.server.eval_results_query(
            tsi.EvalResultsQueryReq(
                project_id=project_id,
                evaluation_call_ids=[eval_root_id],
                require_intersection=False,
                include_rows=False,
                include_summary=True,
                summary_require_intersection=False,
            )
        ).summary

        combined_query = client.server.eval_results_query(
            tsi.EvalResultsQueryReq(
                project_id=project_id,
                evaluation_call_ids=[eval_root_id],
                require_intersection=True,
                include_raw_data_rows=True,
                resolve_row_refs=True,
                include_rows=True,
                include_summary=True,
                summary_require_intersection=False,
            )
        )

        assert combined_query.total_rows == separate_query.total_rows
        assert [r.model_dump() for r in combined_query.rows] == [
            r.model_dump() for r in separate_query.rows
        ]
        assert combined_query.summary is not None
        assert combined_query.summary.model_dump() == separate_summary.model_dump()
