import black
import pytest

import weave
from weave.legacy.weave import panels

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
            panels.Group(),
            "weave.legacy.weave.panels.panel_group.Group()",
        ),
        (
            lambda: panels.Table(
                weave.legacy.weave.ops.range(1, 100, 1).map(
                    lambda row: weave.legacy.weave.ops_primitives.dict.dict_(
                        x=row,
                        y=weave.legacy.weave.ops_primitives.list_.make_list(
                            a=row,
                        ),
                    )
                )
            ),
            lambda: """weave.legacy.weave.panels.panel_table.Table(
            weave.legacy.weave.ops_arrow.list_range.range(1, 100, 1,).map(
                lambda row: weave.legacy.weave.ops_primitives.dict.dict_(
                    x=row,
                    y=weave.legacy.weave.ops_primitives.list_.make_list(
                        a=row,
                    ),
                ),
            ),
        )""",
        ),
        (
            lambda: panels.Plot(
                weave.legacy.weave.ops.range(1, 100, 1).map(
                    lambda row: weave.legacy.weave.ops_primitives.dict.dict_(
                        x=row,
                        y=row**2,
                    )
                )
            ),
            lambda: """weave.legacy.weave.panels.panel_plot.Plot(
            weave.legacy.weave.ops_arrow.list_range.range(1, 100, 1,).map(
                lambda row: weave.legacy.weave.ops_primitives.dict.dict_(
                    x=row,
                    y=row.powBinary(2,),
                ),
            ),
        )""",
        ),
        (
            lambda: panels.Group(
                items={
                    "table": panels.Table(
                        weave.legacy.weave.ops.range(1, 100, 1),
                        columns=[
                            lambda row: row,
                            lambda row: row**2,
                        ],
                    ),
                    "all_rows": lambda table: panels.Plot(
                        table.all_rows(),
                        x=lambda row: row["c_0"],
                        y=lambda row: row["c_1"],
                    ),
                    "derived": lambda table: panels.Group(
                        layoutMode="horizontal",
                        items={
                            "rows": panels.Group(
                                items={
                                    "pinned_rows": panels.Plot(
                                        table.pinned_rows(),
                                        x=lambda row: row["c_0"],
                                        y=lambda row: row["c_1"],
                                    ),
                                    "active_row": table.active_row(),
                                }
                            ),
                            "data": panels.Group(
                                items={
                                    "pinned_data": table.pinned_data(),
                                    "active_data": table.active_data(),
                                }
                            ),
                        },
                    ),
                }
            ),
            lambda: """weave.legacy.weave.panels.panel_group.Group(
    items={
        "table": weave.legacy.weave.panels.panel_table.Table(
            weave.legacy.weave.ops_arrow.list_range.range(1, 100, 1,),
            columns=[
                lambda row: row,
                lambda row: row.powBinary(2,),
            ],
        ),
        "all_rows": lambda table: weave.legacy.weave.panels.panel_plot.Plot(
            table.all_rows(),
            x=lambda row: row["c_0"],
            y=lambda row: row["c_1"],
        ),
        "derived": lambda table, all_rows: weave.legacy.weave.panels.panel_group.Group(
            layoutMode="horizontal",
            items={
                "rows": weave.legacy.weave.panels.panel_group.Group(
                    items={
                        "pinned_rows": weave.legacy.weave.panels.panel_plot.Plot(
                            table.pinned_rows(),
                            x=lambda row: row["c_0"],
                            y=lambda row: row["c_1"],
                        ),
                        "active_row": lambda pinned_rows: table.active_row(),
                    },
                ),
                "data": lambda rows: weave.legacy.weave.panels.panel_group.Group(
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
        panels.Group(
            items={
                "plot": panels.Plot(
                    weave.legacy.weave.ops.local_path(cereal_csv).readcsv(),
                    x=lambda row: row["protein"],
                    y=lambda row: row["calories"],
                ),
                "table": lambda plot: panels.Table(
                    plot.selected_rows(),
                    columns=[
                        lambda row: row["c_0"],
                        lambda row: row["c_1"],
                    ],
                ),
            }
        ),
        '''weave.legacy.weave.panels.panel_group.Group(
        items={
            "plot": weave.legacy.weave.panels.panel_plot.Plot(
                weave.legacy.weave.ops.local_path("'''
        + cereal_csv
        + """",).readcsv(),
                x=lambda row: row["protein"],
                y=lambda row: row["calories"],
            ),
            "table": lambda plot: weave.legacy.weave.panels.panel_table.Table(
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
        panels.Plot(
            weave.legacy.weave.ops.local_path(cereal_csv).readcsv(),
            x=lambda row: row["protein"],
            y=lambda row: row["calories"],
        ),
        f"""weave.legacy.weave.panels.panel_plot.Plot(
    weave.legacy.weave.ops.local_path('{cereal_csv}',).readcsv(),
    x=lambda row: row["protein"],
    y=lambda row: row["calories"],
)""",
    )


def test_table_case(cereal_csv, consistent_table_col_ids):
    _test_object_codification(
        panels.Table(
            weave.legacy.weave.ops.local_path(cereal_csv).readcsv(),
            columns=[
                lambda row: row["protein"],
                lambda row: row["calories"],
            ],
        ),
        f"""weave.legacy.weave.panels.panel_table.Table(
    weave.legacy.weave.ops.local_path('{cereal_csv}',).readcsv(),
    columns=[
        lambda row: row["protein"],
        lambda row: row["calories"],
    ],
)""",
    )


def _test_object_codification(panel, code=None):
    panel_code = weave.legacy.weave.codify.object_to_code(panel)

    generated_panel = eval(panel_code)

    panel_json = weave.storage.to_python(panel)
    generated_panel_json = weave.storage.to_python(generated_panel)

    assert panel_json == generated_panel_json

    if code:
        assert panel_code == black.format_str(code, mode=black.FileMode())
