import weave

# TODO: we need to actually execute the refine_output_type on dict pick before chaining the next op.
# Maybe we can just do this as the execute level and skip figuring this out at the dispatch level.
# yeah, because doung this correctly is going to require a significant refactor of the dispatch code.


def test_end_to_end_query():
    node = weave.ops.project("timssweeney", "keras_learning_rate")
    node = node.filteredRuns('{"name":"4rbxec57"}', "+createdAt")
    node = node.limit(1)
    node = node.summary()
    node = node["validation_predictions"]
    node = node.table()
    node = node.rows()
    node = node.dropna()
    node = node.concat()
    node = node.createIndexCheckpointTag()
    node = node[4]
    node = node["output:max_class.label"]
    assert weave.use(node) == "ship"
