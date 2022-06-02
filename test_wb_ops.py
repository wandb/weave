import weave


def test_wb_ops():
    def body(row):
        return row.type_()

    # group_fn = weave.define_fn(
    #     {"row": ops.ArtifactType()}, lambda row: row.type().name()
    # )
    group_fn = weave.define_fn(
        {"row": weave.ops.RunType()},
        lambda row: weave.ops.dict_(jobtype=row.jobtype()),
    )
    runs_node = weave.ops.project("stacey", "mendeleev").runs()
    grouped = weave.ops.WeaveJSListInterface.groupby(runs_node, group_fn)
    node = grouped.offset(0).limit(10).count()
    weave.use(node)


test_wb_ops()
