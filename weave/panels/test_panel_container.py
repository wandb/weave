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
            "_property_types": {
                "config": {
                    "_property_types": {
                        "panels": {
                            "objectType": {
                                "members": [
                                    {
                                        "_property_types": {
                                            "config": {
                                                "_property_types": {
                                                    "max": "int",
                                                    "min": "int",
                                                    "step": "int",
                                                },
                                                "type": "slider_config_type",
                                            },
                                            "id": {
                                                "type": "const",
                                                "val": "slider",
                                                "valType": "string",
                                            },
                                            "input_node": {
                                                "inputTypes": {},
                                                "outputType": "number",
                                                "type": "function",
                                            },
                                        },
                                        "type": "slider_panel_type",
                                    },
                                    {
                                        "_property_types": {
                                            "config": {
                                                "propertyTypes": {},
                                                "type": "typedDict",
                                            },
                                            "id": {
                                                "type": "const",
                                                "val": "number",
                                                "valType": "string",
                                            },
                                            "input_node": {
                                                "inputTypes": {},
                                                "outputType": "number",
                                                "type": "function",
                                            },
                                        },
                                        "type": "number_panel_type",
                                    },
                                ],
                                "type": "union",
                            },
                            "type": "list",
                        },
                        "variables": {
                            "propertyTypes": {"slider_value": "int"},
                            "type": "typedDict",
                        },
                    },
                    "panels": {
                        "objectType": {
                            "members": [
                                {
                                    "_property_types": {
                                        "config": {
                                            "_property_types": {
                                                "max": "int",
                                                "min": "int",
                                                "step": "int",
                                            },
                                            "type": "slider_config_type",
                                        },
                                        "id": {
                                            "type": "const",
                                            "val": "slider",
                                            "valType": "string",
                                        },
                                        "input_node": {
                                            "inputTypes": {},
                                            "outputType": "number",
                                            "type": "function",
                                        },
                                    },
                                    "type": "slider_panel_type",
                                },
                                {
                                    "_property_types": {
                                        "config": {
                                            "propertyTypes": {},
                                            "type": "typedDict",
                                        },
                                        "id": {
                                            "type": "const",
                                            "val": "number",
                                            "valType": "string",
                                        },
                                        "input_node": {
                                            "inputTypes": {},
                                            "outputType": "number",
                                            "type": "function",
                                        },
                                    },
                                    "type": "number_panel_type",
                                },
                            ],
                            "type": "union",
                        },
                        "type": "list",
                    },
                    "type": "container_config_type",
                    "variables": {
                        "propertyTypes": {"slider_value": "int"},
                        "type": "typedDict",
                    },
                },
                "id": {"type": "const", "val": "container", "valType": "string"},
            },
            "config": {
                "_property_types": {
                    "panels": {
                        "objectType": {
                            "members": [
                                {
                                    "_property_types": {
                                        "config": {
                                            "_property_types": {
                                                "max": "int",
                                                "min": "int",
                                                "step": "int",
                                            },
                                            "type": "slider_config_type",
                                        },
                                        "id": {
                                            "type": "const",
                                            "val": "slider",
                                            "valType": "string",
                                        },
                                        "input_node": {
                                            "inputTypes": {},
                                            "outputType": "number",
                                            "type": "function",
                                        },
                                    },
                                    "type": "slider_panel_type",
                                },
                                {
                                    "_property_types": {
                                        "config": {
                                            "propertyTypes": {},
                                            "type": "typedDict",
                                        },
                                        "id": {
                                            "type": "const",
                                            "val": "number",
                                            "valType": "string",
                                        },
                                        "input_node": {
                                            "inputTypes": {},
                                            "outputType": "number",
                                            "type": "function",
                                        },
                                    },
                                    "type": "number_panel_type",
                                },
                            ],
                            "type": "union",
                        },
                        "type": "list",
                    },
                    "variables": {
                        "propertyTypes": {"slider_value": "int"},
                        "type": "typedDict",
                    },
                },
                "panels": {
                    "objectType": {
                        "members": [
                            {
                                "_property_types": {
                                    "config": {
                                        "_property_types": {
                                            "max": "int",
                                            "min": "int",
                                            "step": "int",
                                        },
                                        "type": "slider_config_type",
                                    },
                                    "id": {
                                        "type": "const",
                                        "val": "slider",
                                        "valType": "string",
                                    },
                                    "input_node": {
                                        "inputTypes": {},
                                        "outputType": "number",
                                        "type": "function",
                                    },
                                },
                                "type": "slider_panel_type",
                            },
                            {
                                "_property_types": {
                                    "config": {
                                        "propertyTypes": {},
                                        "type": "typedDict",
                                    },
                                    "id": {
                                        "type": "const",
                                        "val": "number",
                                        "valType": "string",
                                    },
                                    "input_node": {
                                        "inputTypes": {},
                                        "outputType": "number",
                                        "type": "function",
                                    },
                                },
                                "type": "number_panel_type",
                            },
                        ],
                        "type": "union",
                    },
                    "type": "list",
                },
                "type": "container_config_type",
                "variables": {
                    "propertyTypes": {"slider_value": "int"},
                    "type": "typedDict",
                },
            },
            "type": "container_panel_type",
        },
        "_val": {
            "config": {
                "panels": [
                    {
                        "_union_id": 0,
                        "config": {"max": 100, "min": 0, "step": 0.1},
                        "id": "slider",
                        "input_node": {
                            "nodeType": "var",
                            "type": "number",
                            "varName": "slider_value",
                        },
                    },
                    {
                        "_union_id": 1,
                        "config": {},
                        "id": "number",
                        "input_node": {
                            "nodeType": "var",
                            "type": "number",
                            "varName": "slider_value",
                        },
                    },
                ],
                "variables": {"slider_value": 5},
            },
            "id": "container",
        },
    }
    assert serialized == expected
