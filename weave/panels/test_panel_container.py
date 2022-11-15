from . import panel_container
from .. import storage
from .. import types
from .. import graph


def test_function_type():
    assert types.TypeRegistry.type_of(
        graph.VarNode(types.Number(), "a")
    ) == types.Function({}, types.Number())


def test_panel_container():
    container = panel_container.Container()
    var = container.config.add_variable("slider_value", types.Number(), 5)
    container.config.add_panel(
        panel_container.Slider(
            input_node=var, config=panel_container.SliderConfig(0, 100, 0.1)
        )
    )
    container.config.add_panel(panel_container.Number(input_node=var))
    serialized = storage.to_python(container)
    expected = {
        "_type": {
            "type": "container_panel_type",
            "_is_object": True,
            "id": {"type": "const", "valType": "string", "val": "container"},
            "config": {
                "type": "container_config_type",
                "_is_object": True,
                "variables": {
                    "type": "typedDict",
                    "propertyTypes": {"slider_value": "int"},
                },
                "panels": {
                    "type": "list",
                    "objectType": {
                        "type": "union",
                        "members": [
                            {
                                "type": "slider_panel_type",
                                "_is_object": True,
                                "id": {
                                    "type": "const",
                                    "valType": "string",
                                    "val": "slider",
                                },
                                "input_node": {
                                    "type": "function",
                                    "inputTypes": {},
                                    "outputType": "number",
                                },
                                "config": {
                                    "type": "slider_config_type",
                                    "_is_object": True,
                                    "min": "int",
                                    "max": "int",
                                    "step": "int",
                                },
                            },
                            {
                                "type": "number_panel_type",
                                "_is_object": True,
                                "id": {
                                    "type": "const",
                                    "valType": "string",
                                    "val": "number",
                                },
                                "input_node": {
                                    "type": "function",
                                    "inputTypes": {},
                                    "outputType": "number",
                                },
                                "config": {"type": "typedDict", "propertyTypes": {}},
                            },
                        ],
                    },
                },
            },
        },
        "_val": {
            "id": "container",
            "config": {
                "variables": {"slider_value": 5},
                "panels": [
                    {
                        "id": "slider",
                        "input_node": {
                            "nodeType": "var",
                            "type": "number",
                            "varName": "slider_value",
                        },
                        "config": {"min": 0, "max": 100, "step": 0.1},
                        "_union_id": 0,
                    },
                    {
                        "id": "number",
                        "input_node": {
                            "nodeType": "var",
                            "type": "number",
                            "varName": "slider_value",
                        },
                        "config": {},
                        "_union_id": 1,
                    },
                ],
            },
        },
    }
    assert serialized == expected
