import black
import pytest
import weave

# IMPORTANT: Do not import other symbols inside of weave
# so that we ensure the produced code only relies on the weave symbol.


@pytest.mark.parametrize(
    "panel, code",
    [
        (1, "1"),
        ("hi", "'hi'"),
        (
            {"a": 1, "b": "hi", "c": True, "d": None},
            "{'a': 1, 'b': 'hi', 'c': True, 'd': None}",
        ),
        (
            weave.panels.Group(),
            "weave.panels.panel_group.Group()",
        ),
        (
            lambda: weave.panels.Table(
                weave.ops.range(1, 100, 1).map(
                    lambda row: weave.ops_primitives.dict.dict_(
                        x=row,
                        y=weave.ops_primitives.list_.make_list(
                            a=row,
                        ),
                    )
                )
            ),
            lambda: """weave.panels.panel_table.Table(
    weave.ops_arrow.list_range.range(1, 100, 1,).map(
        lambda row: weave.ops_primitives.dict.dict_(
            x=row,
            y=weave.ops_primitives.list_.make_list(
                a=row,
            ),
        ),
    ),
)""",
        ),
        (
            lambda: weave.panels.Plot(
                weave.ops.range(1, 100, 1).map(
                    lambda row: weave.ops_primitives.dict.dict_(
                        x=row,
                        y=row**2,
                    )
                )
            ),
            lambda: """weave.panels.panel_plot.Plot(
    weave.ops_arrow.list_range.range(1, 100, 1,).map(
        lambda row: weave.ops_primitives.dict.dict_(
            x=row, 
            y=row.powBinary(2,),
        ),
    ),
)""",
        ),
        (
            lambda: weave.panels.Group(
                items={
                    "table": weave.panels.Table(
                        weave.ops.range(1, 100, 1),
                        columns=[
                            lambda row: row,
                            lambda row: row**2,
                        ],
                    ),
                    "all_rows": lambda table: weave.panels.Plot(
                        table.all_rows(),
                        x=lambda row: row["c_0"],
                        y=lambda row: row["c_1"],
                    ),
                    "derived": lambda table: weave.panels.Group(
                        layoutMode="horizontal",
                        items={
                            "rows": weave.panels.Group(
                                items={
                                    "pinned_rows": weave.panels.Plot(
                                        table.pinned_rows(),
                                        x=lambda row: row["c_0"],
                                        y=lambda row: row["c_1"],
                                    ),
                                    "active_row": table.active_row(),
                                }
                            ),
                            "data": weave.panels.Group(
                                items={
                                    "pinned_data": table.pinned_data(),
                                    "active_data": table.active_data(),
                                }
                            ),
                        },
                    ),
                }
            ),
            lambda: """weave.panels.panel_group.Group(
    items={
        "table": weave.panels.panel_table.Table(
            weave.ops_arrow.list_range.range(1, 100, 1,),
            columns=[
                lambda row: row,
                lambda row: row.powBinary(2,),
            ],
        ),
        "all_rows": lambda table: weave.panels.panel_plot.Plot(
            table.all_rows(),
            x=lambda row: row["c_0"],
            y=lambda row: row["c_1"],
        ),
        "derived": lambda table, all_rows: weave.panels.panel_group.Group(
            layoutMode="horizontal",
            items={
                "rows": weave.panels.panel_group.Group(
                    items={
                        "pinned_rows": weave.panels.panel_plot.Plot(
                            table.pinned_rows(),
                            x=lambda row: row["c_0"],
                            y=lambda row: row["c_1"],
                        ),
                        "active_row": lambda pinned_rows: table.active_row(),
                    },
                ),
                "data": lambda rows: weave.panels.panel_group.Group(
                    items={
                        "pinned_data": table.pinned_data(),
                        "active_data": lambda pinned_data: table.active_data(),
                    },
                ),
            },
        ),
    },
)""",
        ),
    ],
)
def test_generic_export(panel, code, consistent_table_col_ids):
    if callable(panel):
        panel = panel()
    if callable(code):
        code = code()
    _test_object_codification(panel, code)


@pytest.mark.skip(reason="Leaving for tim to fix in his branch")
def test_group_case(cereal_csv, consistent_table_col_ids):
    _test_object_codification(
        weave.panels.Group(
            items={
                "plot": weave.panels.Plot(
                    weave.ops.local_path(cereal_csv).readcsv(),
                    x=lambda row: row["protein"],
                    y=lambda row: row["calories"],
                ),
                "table": lambda plot: weave.panels.Table(
                    plot.selected_rows(),
                    columns=[
                        lambda row: row["c_0"],
                        lambda row: row["c_1"],
                    ],
                ),
            }
        ),
        '''weave.panels.panel_group.Group(
        items={
            "plot": weave.panels.panel_plot.Plot(
                weave.ops.local_path("'''
        + cereal_csv
        + """",).readcsv(),
                x=lambda row: row["protein"],
                y=lambda row: row["calories"],
            ),
            "table": lambda plot: weave.panels.panel_table.Table(
                plot.selected_rows(),
                columns=[
                    lambda row: row["c_0"],
                    lambda row: row["c_1"],
                ],
            ),
        },
    )""",
    )


@pytest.mark.skip(reason="Leaving for tim to fix in his branch")
def test_plot_case(cereal_csv, consistent_table_col_ids):
    _test_object_codification(
        weave.panels.Plot(
            weave.ops.local_path(cereal_csv).readcsv(),
            x=lambda row: row["protein"],
            y=lambda row: row["calories"],
        ),
        f"""weave.panels.panel_plot.Plot(
    weave.ops.local_path('{cereal_csv}',).readcsv(),
    x=lambda row: row["protein"],
    y=lambda row: row["calories"],
)""",
    )


def test_table_case(cereal_csv, consistent_table_col_ids):
    _test_object_codification(
        weave.panels.Table(
            weave.ops.local_path(cereal_csv).readcsv(),
            columns=[
                lambda row: row["protein"],
                lambda row: row["calories"],
            ],
        ),
        f"""weave.panels.panel_table.Table(
    weave.ops.local_path('{cereal_csv}',).readcsv(),
    columns=[
        lambda row: row["protein"],
        lambda row: row["calories"],
    ],
)""",
    )


def _test_object_codification(panel, code=None):
    panel_code = weave.codify.object_to_code(panel)

    generated_panel = eval(panel_code)

    panel_json = weave.storage.to_python(panel)
    generated_panel_json = weave.storage.to_python(generated_panel)

    assert panel_json == generated_panel_json

    if code:
        assert panel_code == black.format_str(code, mode=black.FileMode())
