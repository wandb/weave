from .. import ops as ops
from .. import weave_types as types
from ..ops_domain import wb_domain_types as wdt

from ..ops_domain.artifact_collection_ops import root_all_artifacts

from .. import compile
from ..language_features.tagging.tagged_value_type import TaggedValueType


def test_gql_compilation_with_keys():
    project_node = ops.project("stacey", "mendeleev")
    runs_node = project_node.runs()
    cell_node = runs_node.limit(1).id()
    compiled_node = compile.compile([cell_node])[0]

    run_type_keys = types.TypedDict(
        property_types={
            "id": types.String(),
            "name": types.String(),
        }
    )

    run_edges_type = types.TypedDict(
        property_types={
            "edges": types.List(
                object_type=types.TypedDict(property_types={"node": run_type_keys})
            )
        }
    )

    assert compiled_node.type == TaggedValueType(
        types.TypedDict(
            {
                "project": wdt.ProjectType.with_keys(
                    {
                        "id": types.String(),
                        "name": types.String(),
                        "runs_2057dcd339ea3515a695d28f63f4e288": run_edges_type,
                    }
                )
            }
        ),
        types.List(
            TaggedValueType(
                types.TypedDict({"run": wdt.RunType.with_keys(run_type_keys)}),
                types.String(),
            )
        ),
    )


def test_gql_compilation_root_op_custom_key_fn():
    root = root_all_artifacts().limit(1).id()
    compiled_node = compile.compile([root])[0]
    assert compiled_node.type == types.List(types.String())
