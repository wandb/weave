import asyncio

import pytest

import weave
from tests.trace.util import client_is_sqlite
from weave import Evaluation
from weave.trace_server.common_interface import SortBy


def test_filter_calls_by_ref_properties(client):
    """Test filtering calls by values within objects stored as refs in inputs/outputs."""
    if client_is_sqlite(client):
        pytest.skip("Not implemented in SQLite")

    nested1 = {"nested key with spaces": {"one": "1"}}
    nested_ref = weave.publish(nested1, "nested")
    nested2 = {"nested key with spaces": {"one": "2"}}
    nested2_ref = weave.publish(nested2, "nested")

    # Create configuration objects to be referenced
    config1 = {
        "temperature": 0.5,
        "model": "gpt-4",
        "max_tokens": 100,
        "nested": nested_ref,
    }
    config1_ref = weave.publish(config1, "config1")

    config2 = {
        "temperature": 0.8,
        "model": "gpt-3.5",
        "max_tokens": 200,
        "nested": nested2_ref,
    }
    config2_ref = weave.publish(config2, "config2")

    # Create nested objects with references
    worker_info1 = {"id": 1, "status": "active", "config": config1_ref}
    worker1_ref = weave.publish(worker_info1, "worker1")

    worker_info2 = {"id": 2, "status": "inactive", "config": config2_ref}
    worker2_ref = weave.publish(worker_info2, "worker2")

    # Create a more complex nested structure
    project_data = {
        "name": "test_project",
        "version": "v1.0",
        "settings": {"debug": True, "workers": [worker1_ref, worker2_ref]},
    }
    project_ref = weave.publish(project_data, "project")

    @weave.op
    def process_with_config(worker_config, project_info):
        return {
            "processed_worker": worker_config,
            "project_context": project_info,
        }

    # Create calls that use these referenced objects
    process_with_config(worker1_ref, project_ref)
    process_with_config(worker2_ref, project_ref)

    client.flush()

    # Test filtering by simple ref value in inputs
    calls = list(
        client.get_calls(
            query={
                "$expr": {
                    "$eq": [
                        {
                            "$convert": {
                                "input": {"$getField": "inputs.worker_config.id"},
                                "to": "double",
                            }
                        },
                        {"$literal": 1},
                    ]
                }
            },
            expand_columns=["inputs.worker_config"],
        )
    )
    assert len(calls) == 1  # Should get call with worker1

    # Test filtering by nested ref value in inputs
    calls = list(
        client.get_calls(
            query={
                "$expr": {
                    "$eq": [
                        {"$getField": "inputs.worker_config.config.model"},
                        {"$literal": "gpt-4"},
                    ]
                }
            },
            expand_columns=["inputs.worker_config", "inputs.worker_config.config"],
        )
    )
    assert len(calls) == 1  # Should get call with config1 (gpt-4)

    # Test filtering by deeply nested ref with nested value
    calls = list(
        client.get_calls(
            query={
                "$expr": {
                    "$eq": [
                        {"$getField": "inputs.project_info.settings.debug"},
                        {"$literal": "true"},
                    ]
                }
            },
            expand_columns=["inputs.project_info"],
        )
    )
    assert len(calls) == 2  # Should get both calls since both use same project

    # Test filtering by output ref value
    calls = list(
        client.get_calls(
            query={
                "$expr": {
                    "$eq": [
                        {"$getField": "output.processed_worker.status"},
                        {"$literal": "active"},
                    ]
                }
            },
            expand_columns=["output.processed_worker"],
        )
    )
    assert len(calls) == 1  # Should get call that returned worker1

    # Test complex query with multiple ref conditions
    calls = list(
        client.get_calls(
            query={
                "$expr": {
                    "$and": [
                        {
                            "$eq": [
                                {
                                    "$convert": {
                                        "input": {
                                            "$getField": "inputs.worker_config.config.temperature"
                                        },
                                        "to": "double",
                                    }
                                },
                                {"$literal": 0.8},
                            ]
                        },
                        {
                            "$eq": [
                                {"$getField": "inputs.project_info.name"},
                                {"$literal": "test_project"},
                            ]
                        },
                    ]
                }
            },
            expand_columns=[
                "inputs.worker_config",
                "inputs.worker_config.config",
                "inputs.project_info",
            ],
        )
    )
    assert len(calls) == 1  # Should get call with worker2 (temp=0.8) and test_project

    # Test filtering with string comparison on ref values
    calls = list(
        client.get_calls(
            query={
                "$expr": {
                    "$contains": {
                        "input": {"$getField": "inputs.worker_config.config.model"},
                        "substr": {"$literal": "gpt"},
                    }
                }
            },
            expand_columns=["inputs.worker_config", "inputs.worker_config.config"],
        )
    )
    assert len(calls) == 2  # Should get both calls since both models contain "gpt"

    # Test filtering with numeric comparison on ref values in output
    calls = list(
        client.get_calls(
            query={
                "$expr": {
                    "$gt": [
                        {
                            "$convert": {
                                "input": {
                                    "$getField": "output.processed_worker.config.max_tokens"
                                },
                                "to": "double",
                            }
                        },
                        {"$literal": 150},
                    ]
                }
            },
            expand_columns=[
                "output.processed_worker",
                "output.processed_worker.config",
            ],
        )
    )
    assert len(calls) == 1  # Should get call with config2 (max_tokens=200)

    # Test OR condition with ref values
    calls = list(
        client.get_calls(
            query={
                "$expr": {
                    "$or": [
                        {
                            "$eq": [
                                {
                                    "$convert": {
                                        "input": {
                                            "$getField": "inputs.worker_config.id"
                                        },
                                        "to": "double",
                                    }
                                },
                                {"$literal": 1},
                            ]
                        },
                        {
                            "$eq": [
                                {"$getField": "output.processed_worker.status"},
                                {"$literal": "inactive"},
                            ]
                        },
                    ]
                }
            },
            expand_columns=["inputs.worker_config", "output.processed_worker"],
        )
    )
    assert (
        len(calls) == 2
    )  # Should get both calls (worker1 by id=1, worker2 by status=inactive)

    # Test filtering without expand_columns should not work for ref values
    calls = list(
        client.get_calls(
            query={
                "$expr": {
                    "$eq": [
                        {
                            "$convert": {
                                "input": {"$getField": "inputs.worker_config.id"},
                                "to": "double",
                            }
                        },
                        {"$literal": 1},
                    ]
                }
            }
            # No expand_columns provided
        )
    )
    assert len(calls) == 0  # Should get no calls since refs are not expanded

    # Test filtering by deeply nested keys with spaces
    calls = list(
        client.get_calls(
            query={
                "$expr": {
                    "$eq": [
                        {
                            "$getField": "inputs.worker_config.config.nested.nested key with spaces.one"
                        },
                        {"$literal": "1"},
                    ]
                }
            },
            expand_columns=[
                "inputs.worker_config",
                "inputs.worker_config.config",
                "inputs.worker_config.config.nested",
            ],
        )
    )
    assert len(calls) == 1

    # now test that we can order by object ref fields too
    calls = list(
        client.get_calls(
            sort_by=[
                SortBy(
                    field="inputs.worker_config.config.nested.nested key with spaces.one",
                    direction="asc",
                )
            ],
            expand_columns=[
                "inputs.worker_config",
                "inputs.worker_config.config",
                "inputs.worker_config.config.nested",
            ],
        )
    )
    assert (
        calls[0].inputs["worker_config"]["config"]["nested"]["nested key with spaces"][
            "one"
        ]
        == "1"
    )
    assert (
        calls[1].inputs["worker_config"]["config"]["nested"]["nested key with spaces"][
            "one"
        ]
        == "2"
    )

    # desc
    calls = list(
        client.get_calls(
            sort_by=[
                SortBy(
                    field="inputs.worker_config.config.nested.nested key with spaces.one",
                    direction="desc",
                )
            ],
            expand_columns=[
                "inputs.worker_config",
                "inputs.worker_config.config",
                "inputs.worker_config.config.nested",
            ],
        )
    )
    assert (
        calls[0].inputs["worker_config"]["config"]["nested"]["nested key with spaces"][
            "one"
        ]
        == "2"
    )
    assert (
        calls[1].inputs["worker_config"]["config"]["nested"]["nested key with spaces"][
            "one"
        ]
        == "1"
    )


def test_filter_calls_by_ref_properties_with_table_rows_simple(client):
    """Test filtering calls by values within objects stored as refs in inputs/outputs."""
    if client_is_sqlite(client):
        pytest.skip("Not implemented in SQLite")

    # run an evaluation, then delete the evaluation and its children
    @weave.op
    async def model_predict(input) -> str:
        return eval(input)

    object_ref1 = weave.publish({"a": 1, "b": 2}, "object")
    object_ref2 = weave.publish({"a": 3, "b": 4}, "object")
    object_ref3 = weave.publish({"a": 5, "b": 6}, "object")
    object_ref4 = weave.publish({"a": 7, "b": 8}, "object")
    object_ref5 = weave.publish({"a": 9, "b": 10}, "object")

    dataset_rows = [
        {"input": "1+2", "target": 3, "object": object_ref1},
        {"input": "2**4", "target": 15, "object": object_ref2},
        {"input": "3**3", "target": 27, "object": object_ref3},
        {"input": "4**2", "target": 16, "object": object_ref4},
        {"input": "5**1", "target": 5, "object": object_ref5},
    ]

    @weave.op
    async def score(target, model_output, object):
        return target == model_output

    evaluation = Evaluation(
        name="my-eval",
        dataset=dataset_rows,
        scorers=[score],
    )
    asyncio.run(evaluation.evaluate(model_predict))

    calls = list(
        client.get_calls(
            query={
                "$expr": {
                    "$eq": [
                        {"$getField": "inputs.example.input"},
                        {"$literal": "1+2"},
                    ]
                }
            },
            expand_columns=["inputs.example"],
        )
    )
    assert len(calls) == 1

    # get all but the first call
    calls = list(
        client.get_calls(
            query={
                "$expr": {
                    "$gt": [
                        {
                            "$convert": {
                                "input": {"$getField": "inputs.example.target"},
                                "to": "double",
                            }
                        },
                        {"$literal": 3},
                    ]
                }
            },
            expand_columns=["inputs.example"],
        )
    )
    assert len(calls) == 4

    # now order by a table row ref field
    calls = list(
        client.get_calls(
            sort_by=[SortBy(field="inputs.example.target", direction="asc")],
            expand_columns=["inputs.example"],
        )
    )
    assert calls[0].inputs["example"]["target"] == 3
    assert calls[1].inputs["example"]["target"] == 5
    assert calls[2].inputs["example"]["target"] == 15
    assert calls[3].inputs["example"]["target"] == 16
    assert calls[4].inputs["example"]["target"] == 27

    # now order by a table row ref field desc
    calls = list(
        client.get_calls(
            sort_by=[SortBy(field="inputs.example.target", direction="desc")],
            expand_columns=["inputs.example"],
        )
    )
    assert calls[0].inputs["example"]["target"] == 27
    assert calls[1].inputs["example"]["target"] == 16
    assert calls[2].inputs["example"]["target"] == 15
    assert calls[3].inputs["example"]["target"] == 5
    assert calls[4].inputs["example"]["target"] == 3

    # TODO: support filtering by table rows that have objects
    # filter by an object in a row in an eval
    calls = list(
        client.get_calls(
            query={
                "$expr": {
                    "$eq": [
                        {
                            "$convert": {
                                "input": {"$getField": "inputs.example.object.a"},
                                "to": "double",
                            }
                        },
                        {"$literal": 1},
                    ]
                }
            },
            expand_columns=["inputs.example"],
        )
    )
    # TODO: this is broken! You cannot filter by objects that are inside of table_rows!
    # we return 0 but we actually should be returning 1
    assert len(calls) == 0

    # TODO: ordering by objects in table rows is also broken!
    # # now order by a table row ref field
    # calls = list(
    #     client.get_calls(
    #         sort_by=[SortBy(field="inputs.example.object.a", direction="asc")],
    #         expand_columns=["inputs.example"],
    #     )
    # )
    # assert calls[0].inputs["example"]["object"]["a"] == 1
    # assert calls[1].inputs["example"]["object"]["a"] == 3
    # assert calls[2].inputs["example"]["object"]["a"] == 5
    # assert calls[3].inputs["example"]["object"]["a"] == 7
    # assert calls[4].inputs["example"]["object"]["a"] == 9

    # # now order by a table row ref field desc
    # calls = list(
    #     client.get_calls(
    #         sort_by=[SortBy(field="inputs.example.object.a", direction="desc")],
    #         expand_columns=["inputs.example"],
    #     )
    # )
    # assert calls[0].inputs["example"]["object"]["a"] == 9
    # assert calls[1].inputs["example"]["object"]["a"] == 7
    # assert calls[2].inputs["example"]["object"]["a"] == 5
    # assert calls[3].inputs["example"]["object"]["a"] == 3
    # assert calls[4].inputs["example"]["object"]["a"] == 1


def test_mixed_objects_and_refs(client):
    """Test filtering calls by values within objects stored as refs in inputs/outputs."""
    if client_is_sqlite(client):
        pytest.skip("Not implemented in SQLite")

    @weave.op
    def log_config(config: dict) -> None:
        pass

    config1 = {"a": "1", "b": "2"}
    config2 = {"a": "3", "b": "4"}

    log_config(config1)
    log_config(config2)

    @weave.op
    def log_config_ref(config: str) -> None:
        pass

    config1_ref = weave.publish(config1, "config1")
    config2_ref = weave.publish(config2, "config2")

    log_config_ref(config1_ref)
    log_config_ref(config2_ref)

    client.flush()

    # get all calls
    calls = list(client.get_calls())
    assert len(calls) == 4
    assert calls[0].inputs["config"]["a"] == "1"
    assert calls[1].inputs["config"]["a"] == "3"
    assert calls[2].inputs["config"]["a"] == "1"
    assert calls[3].inputs["config"]["a"] == "3"

    # now get all calls, with refs resolved by the trace server
    expand_columns = ["inputs.config"]
    calls = list(client.get_calls(expand_columns=expand_columns))
    assert len(calls) == 4
    assert calls[0].inputs["config"]["a"] == "1"
    assert calls[1].inputs["config"]["a"] == "3"
    assert calls[2].inputs["config"]["a"] == "1"
    assert calls[3].inputs["config"]["a"] == "3"

    # now filter by a normal field without expand_columns
    # we should only get the very first logged call
    query = {"$expr": {"$eq": [{"$getField": "inputs.config.a"}, {"$literal": "1"}]}}
    calls = list(client.get_calls(query=query))
    assert len(calls) == 1
    assert calls[0].inputs["config"]["a"] == "1"
    call1_id = calls[0].id

    # now filter by the same param but resolve the ref
    calls = list(
        client.get_calls(
            query=query,
            expand_columns=expand_columns,
        )
    )
    assert len(calls) == 1
    assert calls[0].inputs["config"]["a"] == "1"
    # still only get one call, but this one is different! its the one with the ref!
    assert calls[0].id != call1_id
