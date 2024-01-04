import weave
from weave.ops_domain import wb_domain_types, runs2


from .. import stitch
from .. import compile_table


def test_runs2_plan():
    runs2.make_runs2_tables(10, 10, 10, 1, 2)
    project = weave.save(
        wb_domain_types.Project.from_keys({"name": "weavetest-10-10-10-2"})
    )
    runs = runs2.runs2(project)
    post_runs = runs.createIndexCheckpointTag()
    post_runs = runs.groupby(lambda run: weave.ops.dict_(k0=run["config"]["key0"]))
    window = post_runs
    nodes = []
    for i in range(10):
        row = window[i]
        for j in range(1, 15):
            nodes.append(row["config"][f"key{j}"])
    p = stitch.stitch(nodes)
    run_cols = compile_table.get_projection(p.get_result(runs))
    assert list(run_cols.keys()) == ["config"]
    assert list(run_cols["config"].keys()) == [f"key{i}" for i in range(15)]
