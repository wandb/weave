# Test for weave.show
# The outputs of weave.show (the generated panel urls and their arguments)
# need to match what javascript expects.

import json

from . import api as weave
from . import ops
from . import storage
from . import graph
from . import panels
from .show import _show_params
from .ecosystem import openai
from . import test_helpers
from . import artifacts_local


def test_show_simple_call():
    csv = ops.local_path("/tmp/cereal.csv").readcsv()
    show_params = _show_params(csv)
    assert show_params["weave_node"].to_json() == {
        "fromOp": {
            "inputs": {
                "self": {
                    "fromOp": {
                        "inputs": {
                            "path": {
                                "nodeType": "const",
                                "type": {
                                    "type": "const",
                                    "valType": "string",
                                    "val": "/tmp/cereal.csv",
                                },
                                "val": "/tmp/cereal.csv",
                            }
                        },
                        "name": "localpath",
                    },
                    "nodeType": "output",
                    "type": {
                        "extension": "csv",
                        "type": "local_file",
                    },
                }
            },
            "name": "file-readcsv",
        },
        "nodeType": "output",
        "type": {
            "objectType": {"keyType": "string", "objectType": "string", "type": "dict"},
            "type": "list",
        },
    }


EXPECTED_SHOW_PARAMS_FINE_TUNE_WEAVE_NODE = {
    "fromOp": {
        "name": "openai-finetunegpt3",
        "inputs": {
            "hyperparameters": {
                "nodeType": "const",
                "type": {
                    "type": "const",
                    "valType": {
                        "type": "typedDict",
                        "propertyTypes": {"n_epochs": "int"},
                    },
                    "val": {"n_epochs": 2},
                },
                "val": {"n_epochs": 2},
            },
            "training_dataset": {
                "fromOp": {
                    "inputs": {
                        "uri": {
                            "nodeType": "const",
                            "type": {
                                "type": "const",
                                "valType": "string",
                                "val": f"local-artifact://{artifacts_local.LOCAL_ARTIFACT_DIR}/list-obj/5826f76113017729abd9aeeef0a14831",
                            },
                            "val": f"local-artifact://{artifacts_local.LOCAL_ARTIFACT_DIR}/list-obj/5826f76113017729abd9aeeef0a14831",
                        }
                    },
                    "name": "get",
                },
                "nodeType": "output",
                "type": {
                    "objectType": {
                        "propertyTypes": {
                            "completion": "string",
                            "id": "int",
                            "prompt": "string",
                        },
                        "type": "typedDict",
                    },
                    "type": "list",
                },
            },
        },
    },
    "nodeType": "output",
    "type": {
        "_history": {"objectType": "any", "type": "list"},
        "_inputs": {"propertyTypes": {}, "type": "typedDict"},
        "_output": {"type": "gpt3-fine-tune-type"},
        "type": "run-type",
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
    show_fine_tune_params = _show_params(fine_tune)

    # print("JSON", show_fine_tune_params["weave_node"].to_json())

    assert (
        show_fine_tune_params["weave_node"].to_json()
        == EXPECTED_SHOW_PARAMS_FINE_TUNE_WEAVE_NODE
    )

    model = openai.Gpt3FineTune.model(fine_tune)
    panel = panels.Table(["1 + 9 =", "2 + 14 ="])
    panel.table_query.add_column(lambda row: row)
    panel.table_query.add_column(lambda row: model.complete(row)["choices"][0]["text"])
    show_panel_params = _show_params(panel)

    # Ensure that we sent the dataset as a get(<ref>) rather than as a const list
    # (this behavior is currently implemented in graph.py:ConstNode)
    panel_config = show_panel_params["panel_config"]
    table_state = panel_config["tableState"]
    col_select_fns = table_state["columnSelectFunctions"]
    col_sel_fn2 = list(col_select_fns.values())[1]
    assert "list-obj/5826f76113017729abd9aeeef0a14831" in json.dumps(col_sel_fn2)

    col_sel_fn2_node = graph.Node.node_from_json(col_sel_fn2)

    # Asserting that weavejs_fixes.remove_opcall_versions_data works
    assert (
        graph.node_expr_str(col_sel_fn2_node)
        == 'get("local-artifact:///tmp/local-artifacts/list-obj/5826f76113017729abd9aeeef0a14831").finetunegpt3({"n_epochs": 2}).model().complete(row).pick("choices").index(0).pick("text")'
    )
