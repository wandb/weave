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
        "type": "any",
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
