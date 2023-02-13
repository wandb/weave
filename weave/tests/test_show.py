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
        "fromOp": {
            "name": "file-readcsv",
            "inputs": {
                "self": {
                    "nodeType": "output",
                    "type": {
                        "type": "local_file",
                        "_base_type": {"type": "FileBase"},
                        "extension": "csv",
                    },
                    "fromOp": {
                        "name": "localpath",
                        "inputs": {
                            "path": {
                                "nodeType": "const",
                                "type": "string",
                                "val": test_helpers.RegexMatcher(".*cereal.csv"),
                            }
                        },
                    },
                }
            },
        },
    }
