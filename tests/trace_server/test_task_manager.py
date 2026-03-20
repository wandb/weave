"""Unit tests for TaskManager using fakeredis."""

import json
from unittest.mock import patch

import fakeredis
import pytest

from weave.trace_server.task_manager import TaskManager


@pytest.fixture
def fake_redis() -> fakeredis.FakeRedis:
    return fakeredis.FakeRedis(decode_responses=True)


@pytest.fixture
def manager(fake_redis: fakeredis.FakeRedis) -> TaskManager:
    with patch(
        "weave.trace_server.task_manager.get_redis_client", return_value=fake_redis
    ):
        return TaskManager(project_id="entity/project", wb_user_id="user123")


def test_create_task(manager: TaskManager) -> None:
    task = manager.create_task(total_items=10)

    assert task["total_items"] == 10
    assert task["successful_items"] == 0
    assert task["failed_items"] == 0
    assert task["canceled_at"] is None
    assert task["created_at"]
    assert task["id"]


def test_get_task_returns_created_task(manager: TaskManager) -> None:
    task = manager.create_task(total_items=5)
    fetched = manager.get_task(task["id"])

    assert fetched == task


def test_get_task_returns_none_for_unknown_id(manager: TaskManager) -> None:
    assert manager.get_task("nonexistent-id") is None


def test_increment_successful_items(manager: TaskManager) -> None:
    task = manager.create_task(total_items=3)
    manager.increment_successful_items(task["id"])
    updated = manager.increment_successful_items(task["id"])

    assert updated is not None
    assert updated["successful_items"] == 2
    assert updated["failed_items"] == 0


def test_increment_failed_items(manager: TaskManager) -> None:
    task = manager.create_task(total_items=3)
    updated = manager.increment_failed_items(task["id"])

    assert updated is not None
    assert updated["failed_items"] == 1
    assert updated["successful_items"] == 0


def test_increment_returns_none_for_unknown_id(manager: TaskManager) -> None:
    assert manager.increment_successful_items("nonexistent-id") is None
    assert manager.increment_failed_items("nonexistent-id") is None


def test_complete_task_removes_it(manager: TaskManager) -> None:
    task = manager.create_task(total_items=1)
    manager.complete_task(task["id"])

    assert manager.get_task(task["id"]) is None


def test_cancel_task_sets_canceled_at(manager: TaskManager) -> None:
    task = manager.create_task(total_items=5)
    assert task["canceled_at"] is None

    canceled = manager.cancel_task(task["id"])

    assert canceled is not None
    assert canceled["canceled_at"] is not None
    fetched = manager.get_task(task["id"])
    assert fetched is not None
    assert fetched["canceled_at"] == canceled["canceled_at"]


def test_cancel_task_returns_none_for_unknown_id(manager: TaskManager) -> None:
    assert manager.cancel_task("nonexistent-id") is None


def test_is_canceled_false_for_new_task(manager: TaskManager) -> None:
    task = manager.create_task(total_items=1)
    assert manager.is_canceled(task["id"]) is False


def test_is_canceled_true_after_cancel(manager: TaskManager) -> None:
    task = manager.create_task(total_items=1)
    manager.cancel_task(task["id"])
    assert manager.is_canceled(task["id"]) is True


def test_is_canceled_false_for_unknown_id(manager: TaskManager) -> None:
    assert manager.is_canceled("nonexistent-id") is False


def test_list_tasks_empty(manager: TaskManager) -> None:
    assert manager.list_tasks() == []


def test_list_tasks_returns_all_tasks(manager: TaskManager) -> None:
    t1 = manager.create_task(total_items=1)
    t2 = manager.create_task(total_items=2)

    tasks = manager.list_tasks()
    ids = {t["id"] for t in tasks}

    assert ids == {t1["id"], t2["id"]}


def test_list_tasks_isolated_by_project_and_user(
    fake_redis: fakeredis.FakeRedis,
) -> None:
    with patch(
        "weave.trace_server.task_manager.get_redis_client", return_value=fake_redis
    ):
        manager_a = TaskManager(project_id="proj/a", wb_user_id="alice")
        manager_b = TaskManager(project_id="proj/b", wb_user_id="alice")

    manager_a.create_task(total_items=1)
    manager_b.create_task(total_items=2)

    assert len(manager_a.list_tasks()) == 1
    assert len(manager_b.list_tasks()) == 1
    assert manager_a.list_tasks()[0]["total_items"] == 1
    assert manager_b.list_tasks()[0]["total_items"] == 2


def test_clear_tasks(manager: TaskManager) -> None:
    manager.create_task(total_items=1)
    manager.create_task(total_items=2)
    assert len(manager.list_tasks()) == 2

    manager.clear_tasks()
    assert manager.list_tasks() == []


def test_task_data_survives_increments(manager: TaskManager) -> None:
    task = manager.create_task(total_items=4)
    manager.increment_successful_items(task["id"])
    manager.increment_successful_items(task["id"])
    manager.increment_failed_items(task["id"])

    final = manager.get_task(task["id"])
    assert final is not None
    assert final["successful_items"] == 2
    assert final["failed_items"] == 1
    assert final["total_items"] == 4
    assert final["canceled_at"] is None


def test_task_key_includes_project_and_user(
    fake_redis: fakeredis.FakeRedis,
) -> None:
    with patch(
        "weave.trace_server.task_manager.get_redis_client", return_value=fake_redis
    ):
        manager = TaskManager(project_id="myentity/myproject", wb_user_id="myuser")

    task = manager.create_task(total_items=1)
    expected_prefix = "weave:task:myentity/myproject:myuser:"
    matching_keys = [k for k in fake_redis.keys("*") if k.startswith(expected_prefix)]

    assert len(matching_keys) == 1
    stored = json.loads(fake_redis.get(matching_keys[0]))
    assert stored["id"] == task["id"]


def test_task_ttl_is_set(fake_redis: fakeredis.FakeRedis) -> None:
    with patch(
        "weave.trace_server.task_manager.get_redis_client", return_value=fake_redis
    ):
        manager = TaskManager(project_id="entity/project", wb_user_id="user123")

    task = manager.create_task(total_items=1)
    key = f"weave:task:entity/project:user123:{task['id']}"
    ttl = fake_redis.ttl(key)

    assert ttl > 0
