"""Mixin for exposing Objects API (V2 API) endpoints on WeaveClient.

This module provides a clean interface for the newer Objects API endpoints,
which provide RESTful interfaces for managing datasets, ops, scorers, and other objects.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Iterator

from weave.trace_server.trace_server_interface import (
    DatasetCreateReq,
    DatasetCreateRes,
    DatasetDeleteReq,
    DatasetDeleteRes,
    DatasetListReq,
    DatasetReadReq,
    DatasetReadRes,
    OpCreateReq,
    OpCreateRes,
    OpDeleteReq,
    OpDeleteRes,
    OpListReq,
    OpReadReq,
    OpReadRes,
    ScorerCreateReq,
    ScorerCreateRes,
    ScorerDeleteReq,
    ScorerDeleteRes,
    ScorerListReq,
    ScorerReadReq,
    ScorerReadRes,
)

if TYPE_CHECKING:
    from weave.trace.weave_client import WeaveClient


class WeaveClientObjectsAPIMixin:
    """Mixin that adds Objects API (V2 API) methods to WeaveClient.

    This mixin provides convenient access to the newer Objects API endpoints,
    which offer cleaner, more RESTful interfaces for managing:
    - Datasets
    - Ops
    - Scorers
    - Models
    - Evaluations
    - And other object types

    The methods in this mixin automatically populate the project_id from the client,
    making the API more ergonomic for end users.
    """

    # Dataset API Methods

    def create_dataset(
        self: WeaveClient,
        rows: list[dict[str, Any]],
        name: str | None = None,
        description: str | None = None,
    ) -> DatasetCreateRes:
        """Create a new dataset in the current project.

        Datasets with the same name will be versioned together.

        Args:
            rows: List of dictionaries representing the dataset rows.
            name: Optional name for the dataset. Datasets with the same name
                  will be versioned together.
            description: Optional description of the dataset.

        Returns:
            DatasetCreateRes with digest, object_id, and version_index.

        Example:
            ```python
            client = weave.init("my-project")
            result = client.create_dataset(
                name="my_dataset",
                rows=[
                    {"input": "hello", "output": "world"},
                    {"input": "foo", "output": "bar"},
                ],
                description="Example dataset"
            )
            print(f"Created dataset version {result.version_index}")
            ```
        """
        req = DatasetCreateReq(
            project_id=self._project_id(),
            name=name,
            description=description,
            rows=rows,
        )
        return self.server.dataset_create(req)

    def get_dataset(
        self: WeaveClient,
        object_id: str,
        digest: str = "latest",
    ) -> DatasetReadRes:
        """Get a specific dataset by ID and version.

        Args:
            object_id: The dataset ID (typically derived from the name).
            digest: The version digest. Can be:
                    - "latest" for the most recent version (default)
                    - "v0", "v1", etc. for specific versions
                    - A full digest string

        Returns:
            DatasetReadRes with dataset metadata and a reference to the rows.

        Example:
            ```python
            client = weave.init("my-project")
            dataset = client.get_dataset("my_dataset", digest="latest")
            print(f"Dataset has {len(dataset.rows)} rows")
            ```
        """
        req = DatasetReadReq(
            project_id=self._project_id(),
            object_id=object_id,
            digest=digest,
        )
        return self.server.dataset_read(req)

    def list_datasets(
        self: WeaveClient,
        limit: int | None = None,
        offset: int | None = None,
    ) -> Iterator[DatasetReadRes]:
        """List all datasets in the current project.

        Args:
            limit: Maximum number of datasets to return.
            offset: Number of datasets to skip (for pagination).

        Returns:
            Iterator of DatasetReadRes objects.

        Example:
            ```python
            client = weave.init("my-project")
            for dataset in client.list_datasets(limit=10):
                print(f"Dataset: {dataset.name}, version: {dataset.version_index}")
            ```
        """
        req = DatasetListReq(
            project_id=self._project_id(),
            limit=limit,
            offset=offset,
        )
        return self.server.dataset_list(req)

    def delete_dataset(
        self: WeaveClient,
        object_id: str,
        digests: list[str] | None = None,
    ) -> DatasetDeleteRes:
        """Delete a dataset or specific versions of a dataset.

        Args:
            object_id: The dataset ID.
            digests: Optional list of version digests to delete.
                     If None, all versions will be deleted.

        Returns:
            DatasetDeleteRes with the number of versions deleted.

        Example:
            ```python
            client = weave.init("my-project")
            # Delete a specific version
            result = client.delete_dataset("my_dataset", digests=["v0"])
            print(f"Deleted {result.num_deleted} version(s)")

            # Delete all versions
            result = client.delete_dataset("my_dataset")
            ```
        """
        req = DatasetDeleteReq(
            project_id=self._project_id(),
            object_id=object_id,
            digests=digests,
        )
        return self.server.dataset_delete(req)

    # Op API Methods

    def create_op(
        self: WeaveClient,
        source_code: str,
        name: str | None = None,
    ) -> OpCreateRes:
        """Create a new op in the current project.

        Ops with the same name will be versioned together.

        Args:
            source_code: Complete Python source code for the op, including imports.
            name: Optional name for the op. Ops with the same name will be
                  versioned together.

        Returns:
            OpCreateRes with digest, object_id, and version_index.

        Example:
            ```python
            client = weave.init("my-project")
            code = '''
            def my_function(x: int) -> int:
                return x * 2
            '''
            result = client.create_op(name="my_op", source_code=code)
            print(f"Created op version {result.version_index}")
            ```
        """
        req = OpCreateReq(
            project_id=self._project_id(),
            name=name,
            source_code=source_code,
        )
        return self.server.op_create(req)

    def get_op(
        self: WeaveClient,
        object_id: str,
        digest: str = "latest",
    ) -> OpReadRes:
        """Get a specific op by ID and version.

        Args:
            object_id: The op ID (typically derived from the name).
            digest: The version digest. Can be:
                    - "latest" for the most recent version (default)
                    - "v0", "v1", etc. for specific versions
                    - A full digest string

        Returns:
            OpReadRes with op metadata and source code.

        Example:
            ```python
            client = weave.init("my-project")
            op = client.get_op("my_op", digest="latest")
            print(f"Op source code:\\n{op.code}")
            ```
        """
        req = OpReadReq(
            project_id=self._project_id(),
            object_id=object_id,
            digest=digest,
        )
        return self.server.op_read(req)

    def list_ops(
        self: WeaveClient,
        limit: int | None = None,
        offset: int | None = None,
    ) -> Iterator[OpReadRes]:
        """List all ops in the current project.

        Args:
            limit: Maximum number of ops to return.
            offset: Number of ops to skip (for pagination).

        Returns:
            Iterator of OpReadRes objects.

        Example:
            ```python
            client = weave.init("my-project")
            for op in client.list_ops(limit=10):
                print(f"Op: {op.object_id}, version: {op.version_index}")
            ```
        """
        req = OpListReq(
            project_id=self._project_id(),
            limit=limit,
            offset=offset,
        )
        return self.server.op_list(req)

    def delete_op(
        self: WeaveClient,
        object_id: str,
        digests: list[str] | None = None,
    ) -> OpDeleteRes:
        """Delete an op or specific versions of an op.

        Args:
            object_id: The op ID.
            digests: Optional list of version digests to delete.
                     If None, all versions will be deleted.

        Returns:
            OpDeleteRes with the number of versions deleted.

        Example:
            ```python
            client = weave.init("my-project")
            # Delete a specific version
            result = client.delete_op("my_op", digests=["v0"])
            print(f"Deleted {result.num_deleted} version(s)")

            # Delete all versions
            result = client.delete_op("my_op")
            ```
        """
        req = OpDeleteReq(
            project_id=self._project_id(),
            object_id=object_id,
            digests=digests,
        )
        return self.server.op_delete(req)

    # Scorer API Methods

    def create_scorer(
        self: WeaveClient,
        name: str,
        op_source_code: str,
        description: str | None = None,
    ) -> ScorerCreateRes:
        """Create a new scorer in the current project.

        Scorers with the same name will be versioned together.

        Args:
            name: Name for the scorer. Scorers with the same name will be
                  versioned together.
            op_source_code: Complete source code for the Scorer.score op,
                            including imports.
            description: Optional description of the scorer.

        Returns:
            ScorerCreateRes with digest, object_id, version_index, and full scorer reference.

        Example:
            ```python
            client = weave.init("my-project")
            code = '''
            def score(output: str, target: str) -> dict:
                return {"exact_match": output == target}
            '''
            result = client.create_scorer(
                name="exact_match_scorer",
                op_source_code=code,
                description="Checks for exact string matches"
            )
            print(f"Created scorer: {result.scorer}")
            ```
        """
        req = ScorerCreateReq(
            project_id=self._project_id(),
            name=name,
            description=description,
            op_source_code=op_source_code,
        )
        return self.server.scorer_create(req)

    def get_scorer(
        self: WeaveClient,
        object_id: str,
        digest: str = "latest",
    ) -> ScorerReadRes:
        """Get a specific scorer by ID and version.

        Args:
            object_id: The scorer ID (typically derived from the name).
            digest: The version digest. Can be:
                    - "latest" for the most recent version (default)
                    - "v0", "v1", etc. for specific versions
                    - A full digest string

        Returns:
            ScorerReadRes with scorer metadata and score op reference.

        Example:
            ```python
            client = weave.init("my-project")
            scorer = client.get_scorer("exact_match_scorer", digest="latest")
            print(f"Scorer: {scorer.name}")
            print(f"Score op: {scorer.score_op}")
            ```
        """
        req = ScorerReadReq(
            project_id=self._project_id(),
            object_id=object_id,
            digest=digest,
        )
        return self.server.scorer_read(req)

    def list_scorers(
        self: WeaveClient,
        limit: int | None = None,
        offset: int | None = None,
    ) -> Iterator[ScorerReadRes]:
        """List all scorers in the current project.

        Args:
            limit: Maximum number of scorers to return.
            offset: Number of scorers to skip (for pagination).

        Returns:
            Iterator of ScorerReadRes objects.

        Example:
            ```python
            client = weave.init("my-project")
            for scorer in client.list_scorers(limit=10):
                print(f"Scorer: {scorer.name}, version: {scorer.version_index}")
            ```
        """
        req = ScorerListReq(
            project_id=self._project_id(),
            limit=limit,
            offset=offset,
        )
        return self.server.scorer_list(req)

    def delete_scorer(
        self: WeaveClient,
        object_id: str,
        digests: list[str] | None = None,
    ) -> ScorerDeleteRes:
        """Delete a scorer or specific versions of a scorer.

        Args:
            object_id: The scorer ID.
            digests: Optional list of version digests to delete.
                     If None, all versions will be deleted.

        Returns:
            ScorerDeleteRes with the number of versions deleted.

        Example:
            ```python
            client = weave.init("my-project")
            # Delete a specific version
            result = client.delete_scorer("my_scorer", digests=["v0"])
            print(f"Deleted {result.num_deleted} version(s)")

            # Delete all versions
            result = client.delete_scorer("my_scorer")
            ```
        """
        req = ScorerDeleteReq(
            project_id=self._project_id(),
            object_id=object_id,
            digests=digests,
        )
        return self.server.scorer_delete(req)
