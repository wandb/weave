# Ideas for ops, but not production ready.

from weave import graph, weave_internal
from ..api import op
from .. import weave_types as types
from .. import api

op(
    name="root-compare_versions",
    input_type={"one_version": types.Any()},
    output_type=types.List(
        types.TypedDict(
            # Hardcode output type for Compare demo right now.
            {"x": types.Float(), "y": types.Float(), "version": types.String()}
        )
    ),
)


def compare_versions(one_version):
    versions = api.versions(one_version)
    data = []
    for i, version in enumerate(versions):
        v_data = version.get()
        label = str(api.expr(version))
        # Is this correct ??
        if isinstance(v_data, graph.Node):
            v_data = weave_internal.use(v_data)
        for row in v_data:
            row.update({"version": label})
            data.append(row)
    return data
