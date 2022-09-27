# Test for weave.show
# The outputs of weave.show (the generated panel urls and their arguments)
# need to match what javascript expects.

import json

from .. import api as weave
from .. import ops
from .. import storage
from .. import graph
from .. import panels
from ..show import _show_params
from ..ecosystem import openai
from . import test_helpers
from .. import artifacts_local
from rich import print


def test_show_simple_call(cereal_csv):
    csv = ops.local_path(cereal_csv).readcsv()
    actual = _show_params(csv)["weave_node"].to_json()
    print("test_show_simple_call.actual", actual)
    assert actual == {
        "nodeType": "output",
        "type": {
            "type": "list",
            "objectType": {"type": "typedDict", "propertyTypes": {}},
        },
        "fromOp": {
            "name": "file-readcsv",
            "inputs": {
                "self": {
                    "nodeType": "output",
                    "type": {
                        "type": "local_file",
                        "extension": "csv",
                        "_property_types": {
                            "extension": {
                                "type": "const",
                                "valType": "string",
                                "val": "csv",
                            },
                            "path": "string",
                            "mtime": "float",
                        },
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


actual_SHOW_PARAMS_FINE_TUNE_WEAVE_NODE = {
    "nodeType": "output",
    "type": {
        "type": "Run",
        "inputs": {"type": "typedDict", "propertyTypes": {}},
        "history": {"type": "list", "objectType": "any"},
        "output": {
            "type": "gpt3_fine_tune_type",
            "_property_types": {
                "id": "string",
                "status": "string",
                "fine_tuned_model": {"type": "union", "members": ["none", "string"]},
                "result_file": {
                    "type": "union",
                    "members": [
                        "none",
                        {
                            "type": "gpt3_fine_tune_results_type",
                            "_property_types": {
                                "bytes": "int",
                                "created_at": "int",
                                "filename": "string",
                                "id": "string",
                                "object": "string",
                                "purpose": {
                                    "type": "const",
                                    "valType": "string",
                                    "val": "fine-tune-results",
                                },
                                "status": "string",
                                "status_details": "none",
                            },
                        },
                    ],
                },
            },
        },
        "_property_types": {
            "id": "string",
            "op_name": "string",
            "state": {
                "type": "union",
                "members": [
                    {"type": "const", "valType": "string", "val": "pending"},
                    {"type": "const", "valType": "string", "val": "running"},
                    {"type": "const", "valType": "string", "val": "finished"},
                    {"type": "const", "valType": "string", "val": "failed"},
                ],
            },
            "prints": {"type": "list", "objectType": "string"},
            "inputs": {"type": "typedDict", "propertyTypes": {}},
            "history": {"type": "list", "objectType": "any"},
            "output": {
                "type": "gpt3_fine_tune_type",
                "_property_types": {
                    "id": "string",
                    "status": "string",
                    "fine_tuned_model": {
                        "type": "union",
                        "members": ["none", "string"],
                    },
                    "result_file": {
                        "type": "union",
                        "members": [
                            "none",
                            {
                                "type": "gpt3_fine_tune_results_type",
                                "_property_types": {
                                    "bytes": "int",
                                    "created_at": "int",
                                    "filename": "string",
                                    "id": "string",
                                    "object": "string",
                                    "purpose": {
                                        "type": "const",
                                        "valType": "string",
                                        "val": "fine-tune-results",
                                    },
                                    "status": "string",
                                    "status_details": "none",
                                },
                            },
                        ],
                    },
                },
            },
        },
    },
    "fromOp": {
        "name": "op-finetune_gpt3",
        "inputs": {
            "training_dataset": {
                "nodeType": "output",
                "type": {"type": "LocalArtifactRef"},
                "fromOp": {
                    "name": "get",
                    "inputs": {
                        "uri": {
                            "nodeType": "const",
                            "type": "string",
                            "val": "local-artifact:///tmp/weave/pytest/weave/tests/test_show.py::test_large_const_node (setup)/list/4cf1abf0d040d897276e4be3c6aa90df",
                        }
                    },
                },
            },
            "hyperparameters": {
                "nodeType": "const",
                "type": {"type": "typedDict", "propertyTypes": {"n_epochs": "int"}},
                "val": {"n_epochs": 2},
            },
        },
    },
}


def test_large_const_node():
    data = []
    for i in range(500):
        a = i
        b = i % 9
        r = a + b
        data.append(
            {"id": i, "prompt": "%s + %s =" % (a, b), "completion": " %s<end>" % r}
        )
    dataset = storage.save(data)
    # storage.save(dataset)
    fine_tune = openai.finetune_gpt3(dataset, {"n_epochs": 2})
    actual = _show_params(fine_tune)["weave_node"].to_json()

    print("test_large_const_node.actual", actual)

    assert actual == actual_SHOW_PARAMS_FINE_TUNE_WEAVE_NODE

    model = openai.Gpt3FineTune.model(fine_tune)
    panel = panels.Table(["1 + 9 =", "2 + 14 ="])
    panel.append_column(lambda row: row)
    panel.append_column(lambda row: model.complete(row)["choices"][0]["text"])
    show_panel_params = _show_params(panel)

    # Ensure that we sent the dataset as a get(<ref>) rather than as a const list
    # (this behavior is currently implemented in graph.py:ConstNode)
    panel_config = show_panel_params["panel_config"]
    table_state = panel_config["tableState"]
    col_select_fns = table_state["columnSelectFunctions"]
    col_sel_fn2 = list(col_select_fns.values())[1]
    assert "list/" in json.dumps(col_sel_fn2)

    col_sel_fn2_node = graph.Node.node_from_json(col_sel_fn2)

    # Asserting that weavejs_fixes.remove_opcall_versions_data works
    assert (
        graph.node_expr_str(col_sel_fn2_node)
        == 'get("local-artifact://%s/list/4cf1abf0d040d897276e4be3c6aa90df").finetune_gpt3({"n_epochs": 2}).model().complete(row).pick("choices").index(0).pick("text")'
        % artifacts_local.local_artifact_dir()
    )
