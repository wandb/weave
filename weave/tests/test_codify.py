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
            "weave.panels.panel_group.Group(config=weave.panels.panel_group.GroupConfig())",
        ),
    ],
)
def test_generic_export(panel, code):
    _test_object_codification(panel, code)


@pytest.mark.skip(reason="Leaving for tim to fix in his branch")
def test_demo_case(cereal_csv):
    _test_object_codification(
        weave.panels.Group(
            items={
                "plot": weave.panels.Plot(
                    weave.ops.local_path(cereal_csv).readcsv(),
                    x=lambda row: row["protein"],
                    y=lambda row: row["calories"],
                ),
                "table": lambda plot: weave.panels.Table(
                    plot.rows_selected(),
                    columns=[
                        lambda row: row["c_0"],
                        lambda row: row["c_1"],
                    ],
                ),
            }
        ),
        None,
    )


@pytest.mark.skip(reason="Leaving for tim to fix in his branch")
def test_plot_case(cereal_csv):
    _test_object_codification(
        weave.panels.Plot(
            weave.ops.local_path(cereal_csv).readcsv(),
            x=lambda row: row["protein"],
            y=lambda row: row["calories"],
        ),
        None,
    )


def _test_object_codification(panel, code=None):
    panel_code = weave.codify.object_to_code(panel)

    generated_panel = eval(panel_code)

    panel_json = weave.storage.to_python(panel)
    generated_panel_json = weave.storage.to_python(generated_panel)

    assert panel_json == generated_panel_json

    if code:
        assert panel_code == black.format_str(code, mode=black.FileMode())
