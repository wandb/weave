from weave_query import weave_types as types
from weave_query.arrow.list_ import ArrowWeaveList, ArrowWeaveListType
from weave_query.decorator_arrow_op import arrow_op
from weave_query.ops_primitives import obj as primitives_obj


@arrow_op(
    name="ArrowWeaveListObject-__vectorizedGetattr__",
    input_type={
        "self": ArrowWeaveListType(types.Any()),
        "name": types.String(),
    },
    output_type=lambda input_types: ArrowWeaveListType(
        primitives_obj.getattr_output_type(
            {"self": input_types["self"].object_type, "name": input_types["name"]}
        )
    ),
    all_args_nullable=False,
)
def arrow_getattr(self, name):
    data = self._arrow_data
    t = types.non_none(self.object_type).property_types()[name]
    if types.optional(self.object_type):
        t = types.optional(t)
    return ArrowWeaveList(data.field(name), t, self._artifact)
