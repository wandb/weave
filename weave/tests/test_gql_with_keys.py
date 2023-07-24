from .. import ops as ops
from .. import weave_types as types
from ..ops_domain import wb_domain_types as wdt

from ..ops_domain.project_ops import root_all_projects

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

    expected = TaggedValueType(
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
                types.TypedDict(
                    {"run": wdt.RunType.with_keys(run_type_keys.property_types)}
                ),
                types.String(),
            )
        ),
    )

    assert compiled_node.type == expected


def test_gql_compilation_root_op_custom_key_fn():
    root = root_all_projects().limit(1)[0].runs().id()
    compiled_node = compile.compile([root])[0]

    run_type = wdt.RunType.with_keys({"id": types.String(), "name": types.String()})
    project_type = wdt.ProjectType.with_keys(
        {
            "id": types.String(),
            "name": types.String(),
            "runs_2057dcd339ea3515a695d28f63f4e288": types.TypedDict(
                {
                    "edges": types.List(
                        types.TypedDict({"node": types.TypedDict(run_type.keys)})
                    )
                }
            ),
        }
    )

    expected = TaggedValueType(
        types.TypedDict({"project": project_type}),
        types.List(TaggedValueType(types.TypedDict({"run": run_type}), types.String())),
    )

    assert compiled_node.type == expected
