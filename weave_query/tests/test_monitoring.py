import contextlib
import os
import time

import pytest

import weave
from weave.legacy.weave.monitoring import monitor

### Skipping some tests here. They are for features that no longer exist. Since we're
# iterating on the API, I'm not removing them yet.


@contextlib.contextmanager
def async_disabled():
    current = os.environ.get("WEAVE_DISABLE_ASYNC_FILE_STREAM")
    os.environ["WEAVE_DISABLE_ASYNC_FILE_STREAM"] = "true"
    try:
        yield
    finally:
        if current is None:
            del os.environ["WEAVE_DISABLE_ASYNC_FILE_STREAM"]
        else:
            os.environ["WEAVE_DISABLE_ASYNC_FILE_STREAM"] = current


@pytest.mark.skip()
def test_monitoring_basic(user_by_api_key_in_env):
    with async_disabled():
        mon = monitor.new_monitor(
            "%s/%s/test_monitoring" % (user_by_api_key_in_env.username, "test")
        )

        @mon.trace()
        def example(a, b):
            return a + b

        rows = []
        results = []
        for i in range(10):
            for j in range(10):
                example(i, j)
                rows.append({"a": i, "b": j})
                results.append(i + j)

        # These underscore accesses are not public API. This is just for testing.
        mon._streamtable.finish()
        node = mon.rows()
        inputs_node = node["inputs"]
        output_node = node["output"]
        input_results, output_results = weave.use([inputs_node, output_node])

        assert input_results.to_pylist_tagged() == rows
        assert output_results.to_pylist_tagged() == results


@pytest.mark.skip("Feature removed")
def test_monitoring_auto_false(user_by_api_key_in_env):
    with async_disabled():
        # @monitoring.monitor(
        #     entity_name=user_by_api_key_in_env.username,
        #     project_name="test",
        #     auto_log=False,
        # )
        def example(a, b):
            return a + b

        rows = []
        results = []
        for i in range(10):
            for j in range(10):
                res = example(i, j)
                res.add_data({"c": i + j})
                results.append(res)
                rows.append(i + j)

        for res in results[::-1]:
            # Do the finishing in reverse order
            res.finalize()

        # These underscore accesses are not public API. This is just for testing.
        example._stream_table.finish()
        node = example.rows()["c"]

        assert weave.use(node).to_pylist_tagged() == rows[::-1]


@pytest.mark.skip("Feature removed")
def test_monitoring_capture_errors(user_by_api_key_in_env):
    with async_disabled():
        # @monitoring.monitor(
        #     entity_name=user_by_api_key_in_env.username,
        #     project_name="test",
        #     raise_on_error=False,
        # )
        def example(a, b):
            if b == 5:
                raise ValueError("5 is bad")
            return a + b

        rows = []
        results = []
        exceptions = []
        for i in range(10):
            for j in range(10):
                example(i, j)
                rows.append({"a": i, "b": j})
                if j == 5:
                    results.append(None)
                    exceptions.append("ValueError: 5 is bad")
                else:
                    results.append(i + j)
                    exceptions.append(None)

        # These underscore accesses are not public API. This is just for testing.
        example._stream_table.finish()
        node = example.rows()

        input_results, output_results, exception_results = weave.use(
            [node["inputs"], node["output"], node["exception"]]
        )

        assert input_results.to_pylist_tagged() == rows
        assert output_results.to_pylist_tagged() == results
        assert exception_results.to_pylist_tagged() == exceptions


@pytest.mark.skip("Feature removed")
def test_monitoring_processors(user_by_api_key_in_env):
    with async_disabled():
        # @monitoring.monitor(
        #     entity_name=user_by_api_key_in_env.username,
        #     project_name="test",
        #     input_preprocessor=lambda a, b: {"val": f"{a} + {b}"},
        #     output_postprocessor=lambda res: {"val": res},
        # )
        def example(a, b):
            return a + b

        rows = []
        results = []
        for i in range(10):
            for j in range(10):
                example(i, j)
                rows.append({"val": f"{i} + {j}"})
                results.append({"val": i + j})

        # These underscore accesses are not public API. This is just for testing.
        example._stream_table.finish()
        node = example.rows()

        input_results, output_results = weave.use([node["inputs"], node["output"]])

        assert input_results.to_pylist_tagged() == rows
        assert output_results.to_pylist_tagged() == results
