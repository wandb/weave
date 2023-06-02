import typing

from .. import codify
from ..api import op, weave_class
from .. import weave_types as types


# This matches the output type logic of the frontend
# We know that this is going to need refinement, but are
# rolling with it in the first iteration. We need to get to the point
# where we don't have all these conditionals.
def getattr_output_type(input_type):
    self_arg = input_type["self"]

    if isinstance(self_arg, types.Const):
        self_arg = self_arg.val_type

    if isinstance(self_arg, types.ObjectType):
        if not isinstance(input_type["name"], types.Const):
            return types.UnknownType()
        key = input_type["name"].val
        property_types = self_arg.property_types()
        return property_types.get(key, types.NoneType())

    if isinstance(self_arg, types.Any):
        return types.Any()

    # TODO: In particular, this branch should go away since
    # we anticipate getattr will eventually just target the
    # object type. This is a temporary special casing until
    # the type hierarchy is properly worked out. For example,
    # here we special case `property_types` and `members` for
    # the typedDict and union types respectively. Then just
    # blindly return a type otherwise. This is just circumstancially
    # correct for now.
    if isinstance(self_arg, types.Type):
        if isinstance(input_type["name"], types.Const):
            if input_type["name"].val == "property_types":
                return types.Dict(types.String(), types.TypeType())
            elif input_type["name"].val == "members":
                return types.List(types.TypeType())
        return types.TypeType()

    return types.Invalid()


def obj_settattr(self, attr, v):
    setattr(self, attr, v)
    return self


@op(
    name="Object-__getattr__",
    setter=obj_settattr,
    input_type={"self": types.ObjectType()},
    output_type=getattr_output_type,
)
def obj_getattr(self, name: str):
    return getattr(self, name, None)


@op(
    name="__internal__-generateCodeForObject",
    input_type={"obj": types.Any()},
    hidden=True,
)
def generate_code_for_object(obj) -> str:
    return codify.object_to_code(obj)
