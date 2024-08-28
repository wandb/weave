import weave
from weave.legacy.weave import ops_arrow
from weave.legacy.weave.wandb_interface.wandb_stream_table import StreamTable


def make_stream_table(*args, **kwargs):
    # Unit test backend does not support async logging
    return StreamTable(*args, **kwargs, _disable_async_file_stream=True)


def test_join_awls_with_stitch(user_by_api_key_in_env):
    # We use StreamTables here because they trigger projection pushdown / stitch,
    # whereas just saving an AWL does not still.
    entity_name = user_by_api_key_in_env.username
    dataset = [{"id": 1, "a": 3, "b": 4}, {"id": 2, "a": 5, "b": 6}]
    dataset_st = make_stream_table(f"{entity_name}/stream-tables/test_table_dataset")
    for row in dataset:
        dataset_st.log(row)
    dataset_st.finish()

    feedback = [{"id": 1, "a": -3, "bb": -4}, {"id": 2, "a": -5, "bb": -6}]
    feedback_st = make_stream_table(f"{entity_name}/stream-tables/test_table_feedback")
    for row in feedback:
        feedback_st.log(row)
    feedback_st.finish()

    joined = weave.legacy.weave.ops.join_2(
        dataset_st.rows(),
        feedback_st.rows(),
        lambda row: row["id"],
        lambda row: row["id"],
        "dataset",
        "feedback",
        True,
        True,
    )
    assert weave.use(joined["dataset.a"]).to_pylist_tagged() == [3, 5]
    assert weave.use(joined["dataset.aa"]).to_pylist_tagged() == [None, None]
    assert weave.use(joined["dataset.b"]).to_pylist_tagged() == [4, 6]
    assert weave.use(joined["feedback.a"]).to_pylist_tagged() == [-3, -5]
    assert weave.use(joined["feedback.bb"]).to_pylist_tagged() == [-4, -6]
    assert weave.use(joined.joinObj()).to_pylist_tagged() == [1, 2]
