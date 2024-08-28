# Test for weave.show
# The outputs of weave.show (the generated panel urls and their arguments)
# need to match what javascript expects.

from weave.legacy.weave import ops

from ...legacy.weave.show import _show_params
from . import test_helpers


def test_show_simple_call(cereal_csv):
    csv = ops.local_path(cereal_csv).readcsv()
    actual = _show_params(csv)["weave_node"].to_json()
    print("test_show_simple_call.actual", actual)
    assert actual == {
        "nodeType": "output",
        "type": "any",
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
