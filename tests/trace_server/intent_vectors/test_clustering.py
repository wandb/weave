from __future__ import annotations

import threading
import time
from contextlib import closing
from datetime import UTC, datetime
from unittest.mock import create_autospec

import pytest

from weave.trace_server.intent_vectors import config
from weave.trace_server.intent_vectors.clustering import (
    ClusterBusyError,
    ClusterJobManager,
)
from weave.trace_server.intent_vectors.models import ClusterJob
from weave.trace_server.intent_vectors.repository import ClusterInput, IntentRepository


def _unit_vector(index: int) -> list[float]:
    vector = [0.0] * config.EMBEDDING_DIMENSIONS
    vector[index] = 1.0
    return vector


def _wait_for_terminal_status(statuses: list[str]) -> None:
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        if statuses and statuses[-1] in {"completed", "failed"}:
            return
        time.sleep(0.01)
    raise AssertionError("cluster job did not finish")


def test_clustering_snapshot_global_slot_results_and_retry() -> None:
    repository = create_autospec(IntentRepository, instance=True)
    repository.has_active_cluster_job.return_value = False
    repository.create_cluster_job.side_effect = lambda project, job, user, size: (
        ClusterJob(
            job_id=job,
            status="queued",
            min_cluster_size=size,
            created_by_user_id=user,
            created_at=datetime.now(UTC),
        )
    )
    repository.load_cluster_inputs.return_value = [
        ClusterInput("a1", 1, _unit_vector(0)),
        ClusterInput("a2", 2, _unit_vector(0)),
        ClusterInput("a3", 3, _unit_vector(0)),
        ClusterInput("b1", 4, _unit_vector(1)),
        ClusterInput("b2", 5, _unit_vector(1)),
        ClusterInput("b3", 6, _unit_vector(1)),
        ClusterInput("noise", 7, _unit_vector(2)),
    ]
    loaded = threading.Event()
    release = threading.Event()
    original_inputs = repository.load_cluster_inputs.return_value

    def load_once(_: str) -> list[ClusterInput]:
        loaded.set()
        assert release.wait(timeout=2)
        return original_inputs

    repository.load_cluster_inputs.side_effect = load_once
    statuses: list[str] = []
    repository.update_cluster_job.side_effect = (
        lambda _project, _job, status, **_kwargs: statuses.append(status)
    )

    with closing(ClusterJobManager(repository)) as manager:
        manager.create("project-a", "user-a", 3)
        assert loaded.wait(timeout=2)
        with pytest.raises(ClusterBusyError):
            manager.create("project-b", "user-b", 3)
        release.set()
        _wait_for_terminal_status(statuses)

        assert statuses == ["running", "completed"]
        results = repository.insert_cluster_results.call_args.args[2]
        assert len(results) == 7
        assert {result.input_version for result in results} == set(range(1, 8))
        assert any(result.cluster_id == -1 for result in results)

        # A terminal job releases the one global slot; retry gets a new job ID.
        repository.load_cluster_inputs.side_effect = None
        repository.load_cluster_inputs.return_value = []
        retry = manager.create("project-a", "user-a", 3)
        _wait_for_terminal_status(statuses)
        first_job_id = repository.create_cluster_job.call_args_list[0].args[1]
        assert retry.job_id != first_job_id
