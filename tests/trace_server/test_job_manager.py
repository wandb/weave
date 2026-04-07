"""Unit tests for JobManager using fakeredis."""

from unittest.mock import patch

import fakeredis
import pytest

from weave.trace_server.job_manager import JobManager


@pytest.fixture
def fake_redis() -> fakeredis.FakeRedis:
    return fakeredis.FakeRedis(decode_responses=True)


@pytest.fixture
def manager(fake_redis: fakeredis.FakeRedis) -> JobManager:
    with patch(
        "weave.trace_server.job_manager.get_redis_client", return_value=fake_redis
    ):
        return JobManager(project_id="entity/project", wb_user_id="user123")


def test_create_job(manager: JobManager) -> None:
    job = manager.create_job(total_items=10)

    assert job.total_items == 10
    assert job.successful_items == 0
    assert job.failed_items == 0
    assert job.canceled_at is None
    assert job.created_at
    assert job.id


def test_get_job_returns_created_job(manager: JobManager) -> None:
    job = manager.create_job(total_items=5)
    fetched = manager.get_job(job.id)

    assert fetched == job


def test_get_job_returns_none_for_unknown_id(manager: JobManager) -> None:
    assert manager.get_job("nonexistent-id") is None


def test_increment_successful_items(manager: JobManager) -> None:
    job = manager.create_job(total_items=3)
    manager.increment_successful_items(job.id)
    updated = manager.increment_successful_items(job.id)

    assert updated is not None
    assert updated.successful_items == 2
    assert updated.failed_items == 0


def test_increment_failed_items(manager: JobManager) -> None:
    job = manager.create_job(total_items=3)
    updated = manager.increment_failed_items(job.id)

    assert updated is not None
    assert updated.failed_items == 1
    assert updated.successful_items == 0


def test_increment_returns_none_for_unknown_id(manager: JobManager) -> None:
    assert manager.increment_successful_items("nonexistent-id") is None
    assert manager.increment_failed_items("nonexistent-id") is None


def test_complete_job_removes_it(manager: JobManager) -> None:
    job = manager.create_job(total_items=1)
    manager.complete_job(job.id)

    assert manager.get_job(job.id) is None


def test_cancel_job_sets_canceled_at(manager: JobManager) -> None:
    job = manager.create_job(total_items=5)
    assert job.canceled_at is None

    canceled = manager.cancel_job(job.id)

    assert canceled is not None
    assert canceled.canceled_at is not None
    fetched = manager.get_job(job.id)
    assert fetched is not None
    assert fetched.canceled_at == canceled.canceled_at


def test_cancel_job_returns_none_for_unknown_id(manager: JobManager) -> None:
    assert manager.cancel_job("nonexistent-id") is None


def test_is_canceled_false_for_new_job(manager: JobManager) -> None:
    job = manager.create_job(total_items=1)
    assert manager.is_canceled(job.id) is False


def test_is_canceled_true_after_cancel(manager: JobManager) -> None:
    job = manager.create_job(total_items=1)
    manager.cancel_job(job.id)
    assert manager.is_canceled(job.id) is True


def test_is_canceled_false_for_unknown_id(manager: JobManager) -> None:
    assert manager.is_canceled("nonexistent-id") is False


def test_list_jobs_empty(manager: JobManager) -> None:
    assert manager.list_jobs() == []


def test_list_jobs_returns_all_jobs(manager: JobManager) -> None:
    j1 = manager.create_job(total_items=1)
    j2 = manager.create_job(total_items=2)

    jobs = manager.list_jobs()
    ids = {j.id for j in jobs}

    assert ids == {j1.id, j2.id}


def test_list_jobs_isolated_by_project_and_user(
    fake_redis: fakeredis.FakeRedis,
) -> None:
    with patch(
        "weave.trace_server.job_manager.get_redis_client", return_value=fake_redis
    ):
        manager_a = JobManager(project_id="proj/a", wb_user_id="alice")
        manager_b = JobManager(project_id="proj/b", wb_user_id="alice")

    manager_a.create_job(total_items=1)
    manager_b.create_job(total_items=2)

    assert len(manager_a.list_jobs()) == 1
    assert len(manager_b.list_jobs()) == 1
    assert manager_a.list_jobs()[0].total_items == 1
    assert manager_b.list_jobs()[0].total_items == 2


def test_clear_jobs(manager: JobManager) -> None:
    manager.create_job(total_items=1)
    manager.create_job(total_items=2)
    assert len(manager.list_jobs()) == 2

    manager.clear_jobs()
    assert manager.list_jobs() == []


def test_job_data_survives_increments(manager: JobManager) -> None:
    job = manager.create_job(total_items=4)
    manager.increment_successful_items(job.id)
    manager.increment_successful_items(job.id)
    manager.increment_failed_items(job.id)

    final = manager.get_job(job.id)
    assert final is not None
    assert final.successful_items == 2
    assert final.failed_items == 1
    assert final.total_items == 4
    assert final.canceled_at is None


def test_job_key_includes_project_and_user(
    fake_redis: fakeredis.FakeRedis,
) -> None:
    with patch(
        "weave.trace_server.job_manager.get_redis_client", return_value=fake_redis
    ):
        manager = JobManager(project_id="myentity/myproject", wb_user_id="myuser")

    job = manager.create_job(total_items=1)
    expected_prefix = "weave:job:myentity/myproject:myuser:"
    matching_keys = [
        k
        for k in fake_redis.keys("*")
        if k.startswith(expected_prefix) and not k.endswith(":_index")
    ]

    assert len(matching_keys) == 1
    stored = fake_redis.hgetall(matching_keys[0])
    assert stored["id"] == job.id


def test_job_ttl_is_set(fake_redis: fakeredis.FakeRedis) -> None:
    with patch(
        "weave.trace_server.job_manager.get_redis_client", return_value=fake_redis
    ):
        manager = JobManager(project_id="entity/project", wb_user_id="user123")

    job = manager.create_job(total_items=1)
    key = f"weave:job:entity/project:user123:{job.id}"
    ttl = fake_redis.ttl(key)

    assert ttl > 0
