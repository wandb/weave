from __future__ import annotations

import threading
import uuid
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass
from time import perf_counter
from typing import TYPE_CHECKING

import numpy as np
from sklearn.cluster import HDBSCAN

from weave.trace_server.intent_vectors import config, metrics
from weave.trace_server.intent_vectors.models import ClusterJob, ClusterResult

if TYPE_CHECKING:
    from weave.trace_server.intent_vectors.repository import (
        ClusterInput,
        IntentRepository,
    )


class ClusterBusyError(Exception):
    """Raised when the process-wide clustering slot is occupied."""


@dataclass
class _ClusterProgress:
    vector_count: int = 0
    memory_bytes: int = 0


class ClusterJobManager:
    def __init__(self, repository: IntentRepository) -> None:
        self._repository = repository
        self._executor = ThreadPoolExecutor(
            max_workers=1, thread_name_prefix="intent-clustering"
        )
        self._lock = threading.Lock()
        self._future: Future[None] | None = None

    def create(
        self,
        project_id: str,
        user_id: str,
        min_cluster_size: int,
    ) -> ClusterJob:
        with self._lock:
            if (
                self._future is not None and not self._future.done()
            ) or self._repository.has_active_cluster_job():
                raise ClusterBusyError
            job_id = str(uuid.uuid4())
            job = self._repository.create_cluster_job(
                project_id, job_id, user_id, min_cluster_size
            )
            self._future = self._executor.submit(
                self._run, project_id, job_id, min_cluster_size
            )
            return job

    def close(self) -> None:
        self._executor.shutdown(wait=False, cancel_futures=False)

    def _run(self, project_id: str, job_id: str, min_cluster_size: int) -> None:
        started = perf_counter()
        progress = _ClusterProgress()
        try:
            self._execute_job(project_id, job_id, min_cluster_size, progress)
        except MemoryError:
            self._repository.update_cluster_job(
                project_id,
                job_id,
                "failed",
                vector_count=progress.vector_count,
                error_code="memory_limit",
            )
        except Exception:
            self._repository.update_cluster_job(
                project_id,
                job_id,
                "failed",
                vector_count=progress.vector_count,
                error_code="clustering_failed",
            )
        finally:
            metrics.emit(
                "clustering_run",
                duration_ms=round((perf_counter() - started) * 1000, 3),
                vector_count=progress.vector_count,
                matrix_bytes=progress.memory_bytes,
            )

    def _execute_job(
        self,
        project_id: str,
        job_id: str,
        min_cluster_size: int,
        progress: _ClusterProgress,
    ) -> None:
        self._repository.update_cluster_job(project_id, job_id, "running")
        inputs = self._repository.load_cluster_inputs(project_id)
        progress.vector_count = len(inputs)
        if progress.vector_count > config.MAX_CLUSTER_VECTORS:
            self._repository.update_cluster_job(
                project_id,
                job_id,
                "failed",
                vector_count=progress.vector_count,
                error_code="too_many_vectors",
            )
            return

        results, progress.memory_bytes = _cluster(inputs, min_cluster_size)
        self._repository.insert_cluster_results(project_id, job_id, results)
        self._repository.update_cluster_job(
            project_id,
            job_id,
            "completed",
            vector_count=progress.vector_count,
        )


def _cluster(
    inputs: list[ClusterInput], min_cluster_size: int
) -> tuple[list[ClusterResult], int]:
    vector_count = len(inputs)
    memory_bytes = 0
    if not inputs:
        labels = np.asarray([], dtype=np.int32)
        probabilities = np.asarray([], dtype=np.float32)
    elif vector_count < min_cluster_size:
        labels = np.full(vector_count, -1, dtype=np.int32)
        probabilities = np.zeros(vector_count, dtype=np.float32)
    else:
        matrix = np.asarray([item.vector for item in inputs], dtype=np.float32)
        memory_bytes = int(matrix.nbytes)
        model = HDBSCAN(
            min_cluster_size=min_cluster_size,
            metric="euclidean",
            copy=True,
        ).fit(matrix)
        labels = model.labels_
        probabilities = model.probabilities_
    results = [
        ClusterResult(
            intent_id=item.intent_id,
            input_version=item.version,
            cluster_id=int(labels[index]),
            probability=float(probabilities[index]),
        )
        for index, item in enumerate(inputs)
    ]
    return results, memory_bytes
