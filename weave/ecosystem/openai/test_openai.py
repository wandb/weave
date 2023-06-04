from . import gpt3

from ... import weave_types as types
from .. import openai
from ... import api as weave
from ... import storage
from ... import graph
from .. import panels
from ...show import _show_params


def test_gpt3model_inferred_type():
    assert gpt3.Gpt3Model.complete.input_type.arg_types == {
        "self": gpt3.Gpt3ModelType(),
        "prompt": types.String(),
    }
    assert gpt3.Gpt3Model.complete.concrete_output_type == types.TypedDict(
        {
            "id": types.String(),
            "object": types.String(),
            "created": types.Int(),
            "model": types.String(),
            "choices": types.List(
                types.TypedDict(
                    {
                        "text": types.String(),
                        "index": types.Int(),
                        "logprobs": types.none_type,
                        "finish_reason": types.String(),
                    }
                )
            ),
        }
    )


def test_large_const_node(test_artifact_dir):
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

    ACTUAL_SHOW_PARAMS_FINE_TUNE_WEAVE_NODE = {
        "nodeType": "output",
        "type": {
            "type": "Group",
            "_base_type": {"type": "Panel", "_base_type": {"type": "Object"}},
            "_is_object": True,
            "config": {
                "type": "GroupConfig",
                "_base_type": {"type": "Object"},
                "_is_object": True,
                "items": {
                    "type": "typedDict",
                    "propertyTypes": {
                        "Run": {
                            "type": "function",
                            "inputTypes": {},
                            "outputType": {
                                "type": "Run",
                                "_base_type": {"type": "Object"},
                                "_is_object": True,
                                "id": "string",
                                "op_name": "string",
                                "state": {
                                    "type": "union",
                                    "members": [
                                        {
                                            "type": "const",
                                            "valType": "string",
                                            "val": "pending",
                                        },
                                        {
                                            "type": "const",
                                            "valType": "string",
                                            "val": "running",
                                        },
                                        {
                                            "type": "const",
                                            "valType": "string",
                                            "val": "finished",
                                        },
                                        {
                                            "type": "const",
                                            "valType": "string",
                                            "val": "failed",
                                        },
                                    ],
                                },
                                "prints": {"type": "list", "objectType": "string"},
                                "inputs": {"type": "typedDict", "propertyTypes": {}},
                                "history": {
                                    "type": "list",
                                    "objectType": {
                                        "type": "typedDict",
                                        "propertyTypes": {},
                                    },
                                },
                                "output": {
                                    "type": "gpt3_fine_tune_type",
                                    "_base_type": {"type": "Object"},
                                    "_is_object": True,
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
                                                "_base_type": {
                                                    "type": "openai_stored_file",
                                                    "_base_type": {"type": "Object"},
                                                },
                                                "_is_object": True,
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
                                        ],
                                    },
                                },
                            },
                        }
                    },
                },
                "gridConfig": {
                    "type": "typedDict",
                    "propertyTypes": {
                        "id": "string",
                        "name": "string",
                        "panels": {"type": "list", "objectType": "unknown"},
                        "isOpen": "boolean",
                        "flowConfig": {
                            "type": "typedDict",
                            "propertyTypes": {
                                "snapToColumns": "boolean",
                                "columnsPerPage": "int",
                                "rowsPerPage": "int",
                                "gutterWidth": "int",
                                "boxWidth": "int",
                                "boxHeight": "int",
                            },
                        },
                        "type": "string",
                        "sorted": "int",
                    },
                },
                "liftChildVars": "none",
                "allowedPanels": "none",
                "enableAddPanel": "boolean",
                "childNameBase": "none",
                "layoutMode": "string",
                "showExpressions": "boolean",
                "equalSize": "boolean",
                "style": "string",
            },
            "id": "string",
            "input_node": {
                "type": "function",
                "inputTypes": {},
                "outputType": "unknown",
            },
            "vars": {
                "type": "dict",
                "key_type": "string",
                "objectType": {
                    "type": "function",
                    "inputTypes": {},
                    "outputType": "unknown",
                },
            },
        },
        "fromOp": {
            "name": "get",
            "inputs": {
                "uri": {
                    "nodeType": "const",
                    "type": "string",
                    "val": "local-artifact:///dashboard-Run:latest/obj",
                }
            },
        },
    }
    assert actual == ACTUAL_SHOW_PARAMS_FINE_TUNE_WEAVE_NODE

    model = openai.Gpt3FineTune.model(fine_tune)
    panel = panels.Table(["1 + 9 =", "2 + 14 ="])
    panel.config.tableState.add_column(lambda row: row)
    panel.config.tableState.add_column(
        lambda row: model.complete(row)["choices"][0]["text"]
    )
    show_panel_params = _show_params(panel)
    panel_params = weave.use(show_panel_params["weave_node"])

    panel_config = panel_params.config
    # Ensure that we sent the dataset as a get(<ref>) rather than as a const list
    # (this behavior is currently implemented in graph.py:ConstNode)

    table_state = panel_config.tableState
    col_select_fns = table_state.columnSelectFunctions
    col_sel_fn2 = list(col_select_fns.values())[1]
    assert "list:" in graph.node_expr_str(col_sel_fn2)

    # Asserting that weavejs_fixes.remove_opcall_versions_data works
    assert (
        graph.node_expr_str(col_sel_fn2)
        == 'finetune_gpt3(local-artifact:///list:f909a3e7a090a0a57dbd/obj, {"n_epochs": 2}).model().complete(row)["choices"][0]["text"]'
    )
