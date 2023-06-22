import weave
from weave.wandb_interface.wandb_stream_table import StreamTable


# Example of end to end integration test
def test_stream_logging(user_by_api_key_in_env):
    st = StreamTable("test_table")
    for i in range(10):
        st.log({"hello": f"world_{i}", "index": i, "nested": {"a": [i]}})
    st.finish()

    hist_node = (
        weave.ops.project(user_by_api_key_in_env.username, "stream-tables")
        .run("test_table")
        .history()
    )
    weave.use(hist_node["hello"]) == [f"world_{i}" for i in range(10)]
    weave.use(hist_node["index"]) == [i for i in range(10)]
    weave.use(hist_node["nested"]) == [{"a": [i]} for i in range(10)]
