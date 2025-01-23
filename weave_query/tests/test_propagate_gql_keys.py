import pytest
from weave_query import (
    weave_types as types,
    graph,
    op_def,
    op_args
)
from weave_query.language_features.tagging import (
    tagged_value_type,
)
from weave_query.propagate_gql_keys import _propagate_gql_keys_for_node
from weave_query.ops_domain import wb_domain_types as wdt

def test_mapped_tag_propagation():
    test_op = op_def.OpDef(
        name="run-base_op",
        input_type=op_args.OpNamedArgs({"run": wdt.RunType}),
        output_type=types.List(types.Number()),
        resolve_fn=lambda: None
    )

    mapped_opdef = op_def.OpDef(
        name="mapped_run-base_op",
        input_type=op_args.OpNamedArgs({"run": types.List(wdt.RunType)}),
        output_type=types.List(types.List(types.Number())),
        resolve_fn=lambda: None
    )

    mapped_opdef.derived_from = test_op
    test_op.derived_ops = {"mapped": mapped_opdef}

    test_node = graph.OutputNode(
        types.List(types.Number()),
        "mapped_run-base_op",
        {
            "run": graph.OutputNode(
                tagged_value_type.TaggedValueType(types.TypedDict({"project": wdt.ProjectType}), types.List(wdt.RunType)),
                "limit",
                {
                    "arr": graph.OutputNode(
                        tagged_value_type.TaggedValueType(
                            types.TypedDict({"project": wdt.ProjectType}),
                            types.List(wdt.RunType)
                        ),
                    "project-filteredRuns",
                    {}
            )
        }
            )
        }
    )

    def mock_key_fn(ip, input_type):
        return types.List(types.Number())
    
    result = _propagate_gql_keys_for_node(mapped_opdef, test_node, mock_key_fn, None)

    assert isinstance(result, tagged_value_type.TaggedValueType)
    # existing project tag from inputs flowed to output
    assert result.tag.property_types["project"]
    # run input propagated as tag on output
    assert result.value.object_type.tag.property_types["run"]
    assert isinstance(result.value.object_type.value, types.List)
    assert isinstance(result.value.object_type.value.object_type, types.Number)