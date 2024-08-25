import pytest

from weave.legacy.weave import api, async_demo, ops, runs, storage


def test_run_basic():
    run_id = "TESTRUN"
    run = runs.Run(id=run_id, op_name="test-run")
    run_name = "run-%s:latest" % run_id
    storage.save(run, name=run_name)

    run_node = ops.get(f"local-artifact:///{run_name}/obj")
    assert api.use(run_node.state) == "pending"
    run_node.set_state("running")
    assert api.use(run_node.state) == "running"
    run_node.print("Hello")
    run_node.print("Hello again")
    run_node.log({"x": 49.0})
    run_node.set_output("some-output")

    saved_prints = api.use(run_node.prints)
    assert saved_prints == ["Hello", "Hello again"]
    saved_logs = api.use(run_node._get_prop("history"))
    assert saved_logs == [{"x": 49.0}]
    saved_output = api.use(run_node.output)
    assert saved_output == "some-output"


@pytest.mark.timeout(1.5)
def test_automatic_await():
    twelve = async_demo.slowmult(3, 4, 0.01)
    twenty_four = async_demo.slowmult(2, twelve, 0.01)
    assert api.use(twenty_four.await_final_output()) == 24


@pytest.mark.timeout(1.5)
def test_stable_when_fetching_input():
    dataset = [{"prompt": "a", "completion": "5"}]
    ref = storage.save(dataset)
    get_dataset = ops.get(ref.uri)
    # We're going to fetch a new in memory dataset object for both of these.
    # But we should get the same run ID back because the datasets are the same
    # (which we know by checking that they come from the same ref in the code)
    train1 = async_demo.train(get_dataset)
    train2 = async_demo.train(get_dataset)
    run_id1 = api.use(train1.id())
    run_id2 = api.use(train2.id())
    assert run_id1 == run_id2
    api.use(train1.await_final_output())
    api.use(train2.await_final_output())


@pytest.mark.timeout(1.5)
def test_run_ops():
    twelve = async_demo.slowmult(3, 4, 0.01)

    # We can call any ops that are available on the run's output type.
    # So this should not fail!
    api.use(twelve + 9) == 21


@pytest.mark.timeout(1.5)
def test_run_ops_mapped():
    input = api.save([1, 2])
    result = input.map(
        lambda item: async_demo.slowmult(item, 4, 0.01).await_final_output()
    )

    # We can call any ops that are available on the run's output type.
    # So this should not fail!
    api.use(result) == [5, 6]


@pytest.mark.timeout(1.5)
def test_async_op_expr():
    dataset = api.save([{"prompt": "a", "completion": "5"}])

    train_result = async_demo.train(dataset)
    model = train_result.model()
    saved_model = api.save(model, "model")

    assert (
        str(saved_model)
        == 'get("local-artifact:///list:54643291a9d1a0f06a45/obj").train().model().save("model")'
    )
