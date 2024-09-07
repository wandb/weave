# Ideas for ops, but not production ready.

from weave.legacy.weave import api as api
from weave.legacy.weave import weave_types as types
from weave.legacy.weave.api import op, weave_class

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
        for row in v_data:
            row.update({"version": label})
            data.append(row)
    return data
