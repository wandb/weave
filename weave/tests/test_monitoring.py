import os
import time
from weave import monitoring
import weave


def test_monitoring(user_by_api_key_in_env):
    os.environ["WEAVE_DISABLE_ASYNC_FILE_STREAM"] = "true"

    @monitoring.monitor()
    def example(a, b):
        return a + b

    rows = []
    for i in range(10):
        for j in range(10):
            example(i, j)
            rows.append({"a": i, "b": j})

    # These underscore accesses are not public API. This is just for testing.
    example._stream_table.finish()
    node = example._stream_table._stream_table.rows()["inputs"]

    assert weave.use(node).to_pylist_tagged() == rows
