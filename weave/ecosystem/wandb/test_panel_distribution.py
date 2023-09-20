import random
import weave

from ... import weave_internal
from . import panel_distribution


def test_flow():
    # Simulate what js will do
    # create var nodes for input and config
    items = weave.save(
        [
            {"label": "x", "values": [random.gauss(5, 2) for i in range(5)]},
            {"label": "y", "values": [random.gauss(9, 4) for i in range(5)]},
        ]
    )
    panel = panel_distribution.Distribution(
        items, value_fn=lambda x: x["values"], label_fn=lambda x: x["label"]
    )

    # JS passes weave "functions" (nodes) in, just to ensure this is a pure weave op
    input_var = weave_internal.make_var_node(items.type, "input")
    input_node = weave_internal.make_const_node(weave.type_of(input_var), input_var)
    config_var = weave_internal.make_var_node(weave.type_of(panel.config), "config")
    config_node = weave_internal.make_const_node(weave.type_of(config_var), config_var)

    rendered = weave.use(
        panel_distribution.distribution_panel_plot_render(input_node, config_node)
    )

    rendered_config = rendered.config.series[0]
    plot_select_function_x = rendered_config.table.columnSelectFunctions[
        rendered_config.dims.x
    ]
    plot_select_function_y = rendered_config.table.columnSelectFunctions[
        rendered_config.dims.y
    ]
    plot_select_function_label = rendered_config.table.columnSelectFunctions[
        rendered_config.dims.label
    ]
    assert weave.types.Number().assign_type(plot_select_function_x.type)
    assert weave.types.Int().assign_type(plot_select_function_y.type.value)
    assert weave.types.String().assign_type(plot_select_function_label.type)
