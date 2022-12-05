import weave

from .. import plan

from weave.ops_domain import wb_domain_types
from weave.ecosystem.wandb import runs2, make_runs2_tables


def test_plan1():
    project_node = weave.ops.project("shawn", "fasion-sweep")
    project_name_add_node = project_node.name() + "_hello"
    project_tag_node = weave.ops.project_ops.project_tag_getter_op(
        project_name_add_node
    )
    tag_entity_node = project_tag_node.entity()

    p = plan.plan([tag_entity_node])
    n = p.get_result(project_node)
    assert list(n.cols.keys()) == ["project-name", "project-entity"]


def test_plan2():
    project_node = weave.ops.project("shawn", "fasion-sweep")
    runs_node = project_node.runs()
    runs_node = runs_node.filter(lambda run: run.id() == "run1")
    # runs_jobtype_node = runs_node.jobtype()

    p = plan.plan([runs_node])
    n = p.get_result(project_node)
    assert list(n.cols["project-runs"].cols.keys()) == ["run-id"]


def test_runs_plan():
    make_runs2_tables(100, 10, 10, 10, 10)
    project = weave.save(
        wb_domain_types.Project(
            wb_domain_types.Entity("shawn"), "weavetest-100-10-10-10"
        )
    )
    runs = runs2(project)
    post_runs = runs.createIndexCheckpointTag()
    post_runs = runs.groupby(lambda run: weave.ops.dict_(k0=run["config"]["key0"]))
    window = post_runs
    nodes = []
    for i in range(10):
        row = window[i]
        for j in range(1, 15):
            nodes.append(row["config"][f"key{j}"])
    p = plan.plan(nodes)
    run_cols = p.get_result(runs).cols
    assert len(run_cols) == 1
    assert sorted(plan.get_cols(p, runs)["config"]) == sorted(
        f"key{i}" for i in range(15)
    )
