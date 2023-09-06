import typing

import weave
from .. import dispatch
from .. import weave_internal as internal
from .. import weave_types as types
from .. import weave_internal
from ..panels import panel_group
from ..panels import panel_board
from ..panels_py import panel_autoboard
from .generator_templates import template_registry


# This is not yet general, it describes a board for a specific
# formulation of a text extraction problem


def eval_board(dataset, eval_result0, eval_result1):
    varbar = panel_board.varbar()
    dataset_var = varbar.add("dataset", dataset)
    eval_result0_var = varbar.add("eval_result0", eval_result0)
    eval_result1_var = varbar.add("eval_result1", eval_result1)

    summary = varbar.add(
        "summary",
        weave.ops.make_list(
            a=weave.ops.TypedDict.merge(
                weave.ops.dict_(name="res0"), eval_result0_var["summary"]
            ),
            b=weave.ops.TypedDict.merge(
                weave.ops.dict_(name="res1"), eval_result1_var["summary"]
            ),
        ),
    )

    weave.ops.make_list(
        a=eval_result0_var["eval_table"], b=eval_result0_var["eval_table"]
    )

    concatted_evals = varbar.add(
        "concatted_evals",
        weave.ops.List.concat(
            weave.ops.make_list(
                a=eval_result0_var["eval_table"].map(
                    lambda row: weave.ops.TypedDict.merge(
                        weave.ops.dict_(name="res0"), row
                    )
                ),
                b=eval_result1_var["eval_table"].map(
                    lambda row: weave.ops.TypedDict.merge(
                        weave.ops.dict_(name="res1"), row
                    )
                ),
            )
        ),
    )

    # join evals together first
    joined_evals = varbar.add(
        "joined_evals",
        weave.ops.join_all(
            weave.ops.make_list(
                a=eval_result0_var["eval_table"], b=eval_result1_var["eval_table"]
            ),
            lambda row: row["dataset_id"],
            False,
        ),
    )

    # then join dataset to evals
    dataset_evals = varbar.add(
        "dataset_evals",
        weave.ops.join_2(
            dataset_var,
            joined_evals,
            lambda row: row["id"],
            lambda row: row["dataset_id"][0],
            "dataset",
            "evals",
            False,
            False,
        ),
    )

    main = weave.panels.Group(
        layoutMode="grid",
        showExpressions=True,
        enableAddPanel=True,
    )

    #### Run/config info TODO

    #### Summary info

    main.add(
        "avg_f1",
        weave.panels.Plot(
            summary,
            x=lambda row: row["avg_f1"],
            y=lambda row: row["name"],
            color=lambda row: row["name"],
        ),
        layout=weave.panels.GroupPanelLayout(x=0, y=0, w=12, h=4),
    )

    main.add(
        "latency",
        weave.panels.Plot(
            concatted_evals,
            x=lambda row: row["summary"]["latency"],
            y=lambda row: row["name"],
            color=lambda row: row["name"],
            mark="boxplot",
        ),
        layout=weave.panels.GroupPanelLayout(x=12, y=0, w=12, h=4),
    )

    main.add(
        "field_name_f1",
        weave.panels.Plot(
            summary,
            x=lambda row: row["field_name.f1"],
            y=lambda row: row["name"],
            color=lambda row: row["name"],
        ),
        layout=weave.panels.GroupPanelLayout(x=0, y=4, w=8, h=4),
    )
    main.add(
        "field_shares_f1",
        weave.panels.Plot(
            summary,
            x=lambda row: row["field_shares.f1"],
            y=lambda row: row["name"],
            color=lambda row: row["name"],
        ),
        layout=weave.panels.GroupPanelLayout(x=8, y=4, w=8, h=4),
    )
    main.add(
        "field_directors_f1",
        weave.panels.Plot(
            summary,
            x=lambda row: row["field_directors.f1"],
            y=lambda row: row["name"],
            color=lambda row: row["name"],
        ),
        layout=weave.panels.GroupPanelLayout(x=16, y=4, w=8, h=4),
    )

    # ct = main.add('concat_t', concatted_evals, layout=weave.panels.GroupPanelLayout(x=0, y=4, w=24, h=12))
    # main.add('dataset_table', dataset)
    # main.add('joined_evals', joined_evals)
    # main.add(
    #     "dataset_evals",
    #     dataset_evals,
    #     layout=weave.panels.GroupPanelLayout(x=0, y=4, w=24, h=6),
    # )

    ##### Example details

    # more ideas: show examples that all got wrong, or that are confusing

    # facet_f1 = weave.panels.Facet(
    #     dataset_evals,
    #     x=lambda row: row["evals.summary"][0]["f1"],
    #     y=lambda row: row["evals.summary"][1]["f1"],
    #     select=lambda row: row.count(),
    # )

    # f1_comparison = main.add(
    #     "f1_comparison",
    #     facet_f1,
    #     layout=weave.panels.GroupPanelLayout(x=0, y=8, w=12, h=6),
    # )

    facet_correct = weave.panels.Facet(
        dataset_evals,
        x=lambda row: row["evals.summary"][0]["correct"],
        y=lambda row: row["evals.summary"][1]["correct"],
        select=lambda row: row.count(),
    )

    correct_comparison = main.add(
        "correct_comparison",
        facet_correct,
        layout=weave.panels.GroupPanelLayout(x=0, y=8, w=12, h=6),
    )

    main.add(
        "example_latencies",
        weave.panels.Plot(
            dataset_evals,
            x=lambda row: row["evals.summary"]["latency"][0],
            y=lambda row: row["evals.summary"]["latency"][1],
        ),
        layout=weave.panels.GroupPanelLayout(x=12, y=8, w=12, h=6),
    )

    sel_ex_table = weave.panels.Table(correct_comparison.selected())
    sel_ex_table.config.rowSize = 2
    sel_ex_table.add_column(lambda row: row["dataset.id"], "id")
    sel_ex_table.add_column(lambda row: row["dataset.example"], "example")
    sel_ex_table.add_column(lambda row: row["dataset.label.name"], "label.name")
    sel_ex_table.add_column(
        lambda row: weave.ops.dict_(
            res0=row["evals.result"][0]["name"], res1=row["evals.result"][1]["name"]
        ),
        "result.name",
    )
    sel_ex_table.add_column(lambda row: row["dataset.label.shares"], "label.shares")
    sel_ex_table.add_column(
        lambda row: weave.ops.dict_(
            res0=row["evals.result"][0]["shares"].toString(),
            res1=row["evals.result"][1]["shares"].toString(),
        ),
        "result.shares",
    )
    sel_ex_table.add_column(
        lambda row: row["dataset.label.directors"], "label.directors"
    )
    sel_ex_table.add_column(
        lambda row: weave.ops.dict_(
            res0=row["evals.result"][0]["directors"].toString(),
            res1=row["evals.result"][1]["directors"].toString(),
        ),
        "result.directors",
    )
    sel_ex_table.add_column(
        lambda row: weave.ops.dict_(
            res0=row["evals.summary"][0]["latency"],
            res1=row["evals.summary"][1]["latency"],
        ),
        "latency",
    )

    selected_examples = main.add(
        "selected_examples",
        sel_ex_table,
        layout=weave.panels.GroupPanelLayout(x=0, y=14, w=24, h=12),
    )

    main.add(
        "res0_detail",
        selected_examples.active_data()["evals.summary"][0],
        layout=weave.panels.GroupPanelLayout(x=0, y=26, w=12, h=8),
    )

    main.add(
        "res1_detail",
        selected_examples.active_data()["evals.summary"][1],
        layout=weave.panels.GroupPanelLayout(x=12, y=26, w=12, h=8),
    )

    return weave.panels.Board(vars=varbar, panels=main)
