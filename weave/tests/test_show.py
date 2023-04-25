# Test for weave.show
# The outputs of weave.show (the generated panel urls and their arguments)
# need to match what javascript expects.

from .. import ops
from ..show import _show_params
from . import test_helpers
from rich import print


def test_show_simple_call(cereal_csv):
    csv = ops.local_path(cereal_csv).readcsv()
    actual = _show_params(csv)["weave_node"].to_json()
    print("test_show_simple_call.actual", actual)
    assert actual == {
        "nodeType": "output",
        "type": {
            "type": "Group",
            "_base_type": {"type": "Panel", "_base_type": {"type": "Object"}},
            "_is_object": True,
            "input_node": {
                "type": "function",
                "inputTypes": {},
                "outputType": "invalid",
            },
            "vars": {"type": "typedDict", "propertyTypes": {}},
            "config": {
                "type": "GroupConfig",
                "_base_type": {"type": "Object"},
                "_is_object": True,
                "items": {
                    "type": "typedDict",
                    "propertyTypes": {
                        "table": {
                            "type": "function",
                            "inputTypes": {},
                            "outputType": {
                                "type": "list",
                                "objectType": {
                                    "type": "typedDict",
                                    "propertyTypes": {
                                        "name": "string",
                                        "mfr": "string",
                                        "type": "string",
                                        "calories": "int",
                                        "protein": "int",
                                        "fat": "int",
                                        "sodium": "int",
                                        "fiber": "float",
                                        "carbo": "float",
                                        "sugars": "int",
                                        "potass": "int",
                                        "vitamins": "int",
                                        "shelf": "int",
                                        "weight": "float",
                                        "cups": "float",
                                        "rating": "float",
                                    },
                                },
                            },
                        }
                    },
                },
                "gridConfig": "none",
                "liftChildVars": "none",
                "allowedPanels": "none",
                "enableAddPanel": "none",
                "childNameBase": "none",
                "showExpressions": "boolean",
                "layered": "boolean",
                "preferHorizontal": "boolean",
                "equalSize": "boolean",
                "style": "string",
                "grid": "boolean",
            },
            "id": "string",
        },
        "fromOp": {
            "name": "get",
            "inputs": {
                "uri": {
                    "nodeType": "const",
                    "type": "string",
                    "val": "local-artifact:///dashboard-table:latest/obj",
                }
            },
        },
    }
