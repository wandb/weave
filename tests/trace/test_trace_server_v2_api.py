"""Tests for Trace Server V2 API endpoints.

This module tests the V2 API endpoints for:
- Ops (create, read, list, delete)
- Datasets (create, read, list, delete)
- Scorers (create, read, list, delete)
- Evaluations (create, read, list, delete)

The tests run against both SQLite and ClickHouse backends.
"""

from weave.trace_server import trace_server_interface as tsi


class TestOpsV2API:
    """Tests for Ops V2 API endpoints."""

    def test_op_create_v2(self, client):
        """Test creating an op via V2 API."""
        project_id = client._project_id()

        # Create an op
        req = tsi.OpCreateV2Req(
            project_id=project_id,
            name="test_op",
            source_code="def test_op():\n    return 42",
        )
        res = client.server.op_create_v2(req)

        # Verify response
        assert res.object_id == "test_op"
        assert res.digest is not None
        assert res.version_index == 0

    def test_op_read_v2(self, client):
        """Test reading an op via V2 API."""
        project_id = client._project_id()

        # Create an op first
        source_code = "def my_test_op():\n    return 'hello world'"
        create_req = tsi.OpCreateV2Req(
            project_id=project_id,
            name="readable_op",
            source_code=source_code,
        )
        create_res = client.server.op_create_v2(create_req)

        # Read the op
        read_req = tsi.OpReadV2Req(
            project_id=project_id,
            object_id="readable_op",
            digest=create_res.digest,
        )
        read_res = client.server.op_read_v2(read_req)

        # Verify response
        assert read_res.object_id == "readable_op"
        assert read_res.digest == create_res.digest
        assert read_res.version_index == 0
        assert read_res.code == source_code
        assert read_res.created_at is not None

    def test_op_list_v2(self, client):
        """Test listing ops via V2 API."""
        project_id = client._project_id()

        # Create multiple ops
        for i in range(3):
            req = tsi.OpCreateV2Req(
                project_id=project_id,
                name=f"list_test_op_{i}",
                source_code=f"def op_{i}():\n    return {i}",
            )
            client.server.op_create_v2(req)

        # List ops
        list_req = tsi.OpListV2Req(project_id=project_id)
        ops = list(client.server.op_list_v2(list_req))

        # Verify we get at least our 3 ops
        assert len(ops) >= 3
        op_names = [op.object_id for op in ops]
        assert "list_test_op_0" in op_names
        assert "list_test_op_1" in op_names
        assert "list_test_op_2" in op_names

    def test_op_list_v2_with_limit(self, client):
        """Test listing ops with limit via V2 API."""
        project_id = client._project_id()

        # Create multiple ops
        for i in range(5):
            req = tsi.OpCreateV2Req(
                project_id=project_id,
                name=f"limit_test_op_{i}",
                source_code=f"def op_{i}():\n    return {i}",
            )
            client.server.op_create_v2(req)

        # List ops with limit
        list_req = tsi.OpListV2Req(project_id=project_id, limit=2)
        ops = list(client.server.op_list_v2(list_req))

        # Verify limit is respected
        assert len(ops) == 2

    def test_op_delete_v2(self, client):
        """Test deleting an op via V2 API."""
        project_id = client._project_id()

        # Create an op
        create_req = tsi.OpCreateV2Req(
            project_id=project_id,
            name="deletable_op",
            source_code="def deletable():\n    pass",
        )
        create_res = client.server.op_create_v2(create_req)

        # Delete the op
        delete_req = tsi.OpDeleteV2Req(
            project_id=project_id,
            object_id="deletable_op",
            digests=[create_res.digest],
        )
        delete_res = client.server.op_delete_v2(delete_req)

        # Verify deletion
        assert delete_res.num_deleted == 1

    def test_op_delete_v2_all_versions(self, client):
        """Test deleting all versions of an op via V2 API."""
        project_id = client._project_id()

        # Create multiple versions
        digests = []
        for i in range(3):
            create_req = tsi.OpCreateV2Req(
                project_id=project_id,
                name="multi_version_op",
                source_code=f"def multi_version():\n    return {i}",
            )
            create_res = client.server.op_create_v2(create_req)
            digests.append(create_res.digest)

        # Delete all versions (None means delete all)
        delete_req = tsi.OpDeleteV2Req(
            project_id=project_id,
            object_id="multi_version_op",
            digests=None,
        )
        delete_res = client.server.op_delete_v2(delete_req)

        # Verify all versions deleted
        assert delete_res.num_deleted == 3


class TestDatasetsV2API:
    """Tests for Datasets V2 API endpoints."""

    def test_dataset_create_v2(self, client):
        """Test creating a dataset via V2 API."""
        project_id = client._project_id()

        # Create a dataset
        req = tsi.DatasetCreateV2Req(
            project_id=project_id,
            name="test_dataset",
            description="A test dataset",
            rows=[
                {"input": "hello", "output": "world"},
                {"input": "foo", "output": "bar"},
            ],
        )
        res = client.server.dataset_create_v2(req)

        # Verify response
        assert res.object_id.startswith("dataset_")
        assert res.digest is not None
        assert res.version_index == 0

    def test_dataset_read_v2(self, client):
        """Test reading a dataset via V2 API."""
        project_id = client._project_id()

        # Create a dataset first
        rows = [
            {"question": "What is 2+2?", "answer": "4"},
            {"question": "What is the capital of France?", "answer": "Paris"},
        ]
        create_req = tsi.DatasetCreateV2Req(
            project_id=project_id,
            name="readable_dataset",
            description="Test dataset for reading",
            rows=rows,
        )
        create_res = client.server.dataset_create_v2(create_req)

        # Read the dataset
        read_req = tsi.DatasetReadV2Req(
            project_id=project_id,
            object_id=create_res.object_id,
            digest=create_res.digest,
        )
        read_res = client.server.dataset_read_v2(read_req)

        # Verify response
        assert read_res.object_id == create_res.object_id
        assert read_res.digest == create_res.digest
        assert read_res.version_index == 0
        assert read_res.name == "readable_dataset"
        assert read_res.description == "Test dataset for reading"
        assert read_res.rows is not None  # Field is 'rows', not 'rows_ref'
        assert read_res.created_at is not None

    def test_dataset_list_v2(self, client):
        """Test listing datasets via V2 API."""
        project_id = client._project_id()

        # Create multiple datasets
        for i in range(3):
            req = tsi.DatasetCreateV2Req(
                project_id=project_id,
                name=f"list_dataset_{i}",
                rows=[{"value": i}],
            )
            client.server.dataset_create_v2(req)

        # List datasets
        list_req = tsi.DatasetListV2Req(project_id=project_id)
        datasets = list(client.server.dataset_list_v2(list_req))

        # Verify we get at least our 3 datasets
        assert len(datasets) >= 3
        dataset_names = [ds.name for ds in datasets]
        assert "list_dataset_0" in dataset_names
        assert "list_dataset_1" in dataset_names
        assert "list_dataset_2" in dataset_names

    def test_dataset_delete_v2(self, client):
        """Test deleting a dataset via V2 API."""
        project_id = client._project_id()

        # Create a dataset
        create_req = tsi.DatasetCreateV2Req(
            project_id=project_id,
            name="deletable_dataset",
            rows=[{"data": "test"}],
        )
        create_res = client.server.dataset_create_v2(create_req)

        # Delete the dataset
        delete_req = tsi.DatasetDeleteV2Req(
            project_id=project_id,
            object_id=create_res.object_id,
            digests=[create_res.digest],
        )
        delete_res = client.server.dataset_delete_v2(delete_req)

        # Verify deletion
        assert delete_res.num_deleted == 1


class TestScorersV2API:
    """Tests for Scorers V2 API endpoints."""

    def test_scorer_create_v2(self, client):
        """Test creating a scorer via V2 API."""
        project_id = client._project_id()

        # Create a scorer
        req = tsi.ScorerCreateV2Req(
            project_id=project_id,
            name="test_scorer",
            description="A test scorer",
            op_source_code="def score(output, target):\n    return output == target",
        )
        res = client.server.scorer_create_v2(req)

        # Verify response
        assert res.object_id.startswith("scorer_")
        assert res.digest is not None
        assert res.version_index == 0

    def test_scorer_read_v2(self, client):
        """Test reading a scorer via V2 API."""
        project_id = client._project_id()

        # Create a scorer first
        source_code = (
            "def accuracy_score(output, target):\n    return int(output == target)"
        )
        create_req = tsi.ScorerCreateV2Req(
            project_id=project_id,
            name="accuracy_scorer",
            description="Measures accuracy",
            op_source_code=source_code,
        )
        create_res = client.server.scorer_create_v2(create_req)

        # Read the scorer
        read_req = tsi.ScorerReadV2Req(
            project_id=project_id,
            object_id=create_res.object_id,
            digest=create_res.digest,
        )
        read_res = client.server.scorer_read_v2(read_req)

        # Verify response
        assert read_res.object_id == create_res.object_id
        assert read_res.digest == create_res.digest
        assert read_res.version_index == 0
        assert read_res.name == "accuracy_scorer"
        assert read_res.description == "Measures accuracy"
        assert (
            read_res.score_op is not None
        )  # ScorerReadV2Res has 'score_op', not 'code'
        assert read_res.created_at is not None

    def test_scorer_list_v2(self, client):
        """Test listing scorers via V2 API."""
        project_id = client._project_id()

        # Create multiple scorers
        for i in range(3):
            req = tsi.ScorerCreateV2Req(
                project_id=project_id,
                name=f"list_scorer_{i}",
                op_source_code=f"def scorer_{i}():\n    return {i}",
            )
            client.server.scorer_create_v2(req)

        # List scorers
        list_req = tsi.ScorerListV2Req(project_id=project_id)
        scorers = list(client.server.scorer_list_v2(list_req))

        # Verify we get at least our 3 scorers
        assert len(scorers) >= 3
        scorer_names = [s.name for s in scorers]
        assert "list_scorer_0" in scorer_names
        assert "list_scorer_1" in scorer_names
        assert "list_scorer_2" in scorer_names

    def test_scorer_delete_v2(self, client):
        """Test deleting a scorer via V2 API."""
        project_id = client._project_id()

        # Create a scorer
        create_req = tsi.ScorerCreateV2Req(
            project_id=project_id,
            name="deletable_scorer",
            op_source_code="def deletable():\n    pass",
        )
        create_res = client.server.scorer_create_v2(create_req)

        # Delete the scorer
        delete_req = tsi.ScorerDeleteV2Req(
            project_id=project_id,
            object_id=create_res.object_id,
            digests=[create_res.digest],
        )
        delete_res = client.server.scorer_delete_v2(delete_req)

        # Verify deletion
        assert delete_res.num_deleted == 1


class TestEvaluationsV2API:
    """Tests for Evaluations V2 API endpoints."""

    def test_evaluation_create_v2(self, client):
        """Test creating an evaluation via V2 API."""
        project_id = client._project_id()

        # First create a dataset
        dataset_req = tsi.DatasetCreateV2Req(
            project_id=project_id,
            name="eval_dataset",
            rows=[{"input": "test", "output": "result"}],
        )
        dataset_res = client.server.dataset_create_v2(dataset_req)

        # Create dataset ref
        entity, project = project_id.split("/")
        dataset_ref = f"weave:///{entity}/{project}/object/{dataset_res.object_id}:{dataset_res.digest}"

        # Create an evaluation
        req = tsi.EvaluationCreateV2Req(
            project_id=project_id,
            name="test_evaluation",
            description="A test evaluation",
            dataset=dataset_ref,
            scorers=[],
            trials=1,
        )
        res = client.server.evaluation_create_v2(req)

        # Verify response
        assert res.object_id == "test_evaluation"  # Evaluations use name as object_id
        assert res.digest is not None
        assert res.version_index == 0
        assert res.evaluation_ref is not None

    def test_evaluation_read_v2(self, client):
        """Test reading an evaluation via V2 API."""
        project_id = client._project_id()

        # Create dataset and evaluation first
        dataset_req = tsi.DatasetCreateV2Req(
            project_id=project_id,
            name="read_eval_dataset",
            rows=[{"data": "value"}],
        )
        dataset_res = client.server.dataset_create_v2(dataset_req)

        entity, project = project_id.split("/")
        dataset_ref = f"weave:///{entity}/{project}/object/{dataset_res.object_id}:{dataset_res.digest}"

        eval_req = tsi.EvaluationCreateV2Req(
            project_id=project_id,
            name="readable_evaluation",
            description="Test eval for reading",
            dataset=dataset_ref,
            scorers=[],
            trials=2,
            evaluation_name="custom_eval_name",
        )
        eval_res = client.server.evaluation_create_v2(eval_req)

        # Read the evaluation
        read_req = tsi.EvaluationReadV2Req(
            project_id=project_id,
            object_id=eval_res.object_id,
            digest=eval_res.digest,
        )
        read_res = client.server.evaluation_read_v2(read_req)

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

    def test_evaluation_list_v2(self, client):
        """Test listing evaluations via V2 API."""
        project_id = client._project_id()

        # Create dataset
        dataset_req = tsi.DatasetCreateV2Req(
            project_id=project_id,
            name="list_eval_dataset",
            rows=[{"x": 1}],
        )
        dataset_res = client.server.dataset_create_v2(dataset_req)

        entity, project = project_id.split("/")
        dataset_ref = f"weave:///{entity}/{project}/object/{dataset_res.object_id}:{dataset_res.digest}"

        # Create multiple evaluations
        for i in range(3):
            req = tsi.EvaluationCreateV2Req(
                project_id=project_id,
                name=f"list_evaluation_{i}",
                dataset=dataset_ref,
                scorers=[],
            )
            client.server.evaluation_create_v2(req)

        # List evaluations
        list_req = tsi.EvaluationListV2Req(project_id=project_id)
        evaluations = list(client.server.evaluation_list_v2(list_req))

        # Verify we get at least our 3 evaluations
        assert len(evaluations) >= 3
        eval_names = [ev.name for ev in evaluations]
        assert "list_evaluation_0" in eval_names
        assert "list_evaluation_1" in eval_names
        assert "list_evaluation_2" in eval_names

    def test_evaluation_delete_v2(self, client):
        """Test deleting an evaluation via V2 API."""
        project_id = client._project_id()

        # Create dataset and evaluation
        dataset_req = tsi.DatasetCreateV2Req(
            project_id=project_id,
            name="delete_eval_dataset",
            rows=[{"data": "test"}],
        )
        dataset_res = client.server.dataset_create_v2(dataset_req)

        entity, project = project_id.split("/")
        dataset_ref = f"weave:///{entity}/{project}/object/{dataset_res.object_id}:{dataset_res.digest}"

        eval_req = tsi.EvaluationCreateV2Req(
            project_id=project_id,
            name="deletable_evaluation",
            dataset=dataset_ref,
            scorers=[],
        )
        eval_res = client.server.evaluation_create_v2(eval_req)

        # Delete the evaluation
        delete_req = tsi.EvaluationDeleteV2Req(
            project_id=project_id,
            object_id=eval_res.object_id,
            digests=[eval_res.digest],
        )
        delete_res = client.server.evaluation_delete_v2(delete_req)

        # Verify deletion
        assert delete_res.num_deleted == 1

    def test_evaluation_with_scorers(self, client):
        """Test creating an evaluation with scorers."""
        project_id = client._project_id()

        # Create dataset
        dataset_req = tsi.DatasetCreateV2Req(
            project_id=project_id,
            name="scorer_eval_dataset",
            rows=[{"input": "test", "expected": "output"}],
        )
        dataset_res = client.server.dataset_create_v2(dataset_req)

        # Create scorers
        scorer_req1 = tsi.ScorerCreateV2Req(
            project_id=project_id,
            name="scorer_1",
            op_source_code="def score1():\n    return 1",
        )
        scorer_res1 = client.server.scorer_create_v2(scorer_req1)

        scorer_req2 = tsi.ScorerCreateV2Req(
            project_id=project_id,
            name="scorer_2",
            op_source_code="def score2():\n    return 2",
        )
        scorer_res2 = client.server.scorer_create_v2(scorer_req2)

        # Build refs
        entity, project = project_id.split("/")
        dataset_ref = f"weave:///{entity}/{project}/object/{dataset_res.object_id}:{dataset_res.digest}"
        scorer_ref1 = f"weave:///{entity}/{project}/object/{scorer_res1.object_id}:{scorer_res1.digest}"
        scorer_ref2 = f"weave:///{entity}/{project}/object/{scorer_res2.object_id}:{scorer_res2.digest}"

        # Create evaluation with scorers
        eval_req = tsi.EvaluationCreateV2Req(
            project_id=project_id,
            name="eval_with_scorers",
            dataset=dataset_ref,
            scorers=[scorer_ref1, scorer_ref2],
        )
        eval_res = client.server.evaluation_create_v2(eval_req)

        # Read it back and verify scorers
        read_req = tsi.EvaluationReadV2Req(
            project_id=project_id,
            object_id=eval_res.object_id,
            digest=eval_res.digest,
        )
        read_res = client.server.evaluation_read_v2(read_req)

        assert len(read_res.scorers) == 2
        assert scorer_ref1 in read_res.scorers
        assert scorer_ref2 in read_res.scorers


class TestV2APIIntegration:
    """Integration tests for V2 API endpoints."""

    def test_complete_evaluation_workflow(self, client):
        """Test a complete workflow: create dataset, scorers, and evaluation."""
        project_id = client._project_id()
        entity, project = project_id.split("/")

        # Step 1: Create a dataset
        dataset_req = tsi.DatasetCreateV2Req(
            project_id=project_id,
            name="workflow_dataset",
            description="Dataset for workflow test",
            rows=[
                {"question": "What is 2+2?", "answer": "4"},
                {"question": "What is 3+3?", "answer": "6"},
            ],
        )
        dataset_res = client.server.dataset_create_v2(dataset_req)
        dataset_ref = f"weave:///{entity}/{project}/object/{dataset_res.object_id}:{dataset_res.digest}"

        # Step 2: Create scorers
        exact_match_req = tsi.ScorerCreateV2Req(
            project_id=project_id,
            name="exact_match",
            description="Checks for exact match",
            op_source_code="def score(output, answer):\n    return output == answer",
        )
        exact_match_res = client.server.scorer_create_v2(exact_match_req)
        exact_match_ref = f"weave:///{entity}/{project}/object/{exact_match_res.object_id}:{exact_match_res.digest}"

        length_req = tsi.ScorerCreateV2Req(
            project_id=project_id,
            name="length_check",
            description="Checks answer length",
            op_source_code="def score(output):\n    return len(output)",
        )
        length_res = client.server.scorer_create_v2(length_req)
        length_ref = f"weave:///{entity}/{project}/object/{length_res.object_id}:{length_res.digest}"

        # Step 3: Create evaluation
        eval_req = tsi.EvaluationCreateV2Req(
            project_id=project_id,
            name="math_evaluation",
            description="Evaluates math questions",
            dataset=dataset_ref,
            scorers=[exact_match_ref, length_ref],
            trials=3,
            evaluation_name="Math Quiz v1",
        )
        eval_res = client.server.evaluation_create_v2(eval_req)

        # Step 4: Verify all components exist and are linked
        # Read evaluation
        eval_read_req = tsi.EvaluationReadV2Req(
            project_id=project_id,
            object_id=eval_res.object_id,
            digest=eval_res.digest,
        )
        eval_read_res = client.server.evaluation_read_v2(eval_read_req)

        assert eval_read_res.name == "math_evaluation"
        assert eval_read_res.dataset == dataset_ref
        assert len(eval_read_res.scorers) == 2
        assert exact_match_ref in eval_read_res.scorers
        assert length_ref in eval_read_res.scorers
        assert eval_read_res.trials == 3
        assert eval_read_res.evaluation_name == "Math Quiz v1"

        # Verify we can read the dataset
        dataset_read_req = tsi.DatasetReadV2Req(
            project_id=project_id,
            object_id=dataset_res.object_id,
            digest=dataset_res.digest,
        )
        dataset_read_res = client.server.dataset_read_v2(dataset_read_req)
        assert dataset_read_res.name == "workflow_dataset"

        # Verify we can read the scorers
        scorer1_read_req = tsi.ScorerReadV2Req(
            project_id=project_id,
            object_id=exact_match_res.object_id,
            digest=exact_match_res.digest,
        )
        scorer1_read_res = client.server.scorer_read_v2(scorer1_read_req)
        assert scorer1_read_res.name == "exact_match"

        scorer2_read_req = tsi.ScorerReadV2Req(
            project_id=project_id,
            object_id=length_res.object_id,
            digest=length_res.digest,
        )
        scorer2_read_res = client.server.scorer_read_v2(scorer2_read_req)
        assert scorer2_read_res.name == "length_check"

    def test_versioning_workflow(self, client):
        """Test that versioning works correctly across V2 API."""
        project_id = client._project_id()

        # Create multiple versions of the same op
        versions = []
        for i in range(3):
            req = tsi.OpCreateV2Req(
                project_id=project_id,
                name="versioned_op",
                source_code=f"def versioned():\n    return {i}",
            )
            res = client.server.op_create_v2(req)
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
            read_req = tsi.OpReadV2Req(
                project_id=project_id,
                object_id="versioned_op",
                digest=version.digest,
            )
            read_res = client.server.op_read_v2(read_req)
            assert read_res.digest == version.digest
            assert read_res.version_index == version.version_index
