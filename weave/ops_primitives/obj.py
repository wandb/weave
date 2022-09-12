from ..api import op, weave_class
from .. import weave_types as types

# This matches the output type logic of the frontend
# We know that this is going to need refinement, but are
# rolling with it in the first iteration. We need to get to the point
# where we don't have all these conditionals.
def getattr_output_type(input_type):
    self_arg = input_type["self"]

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
                return types.Dict(types.String(), types.Type())
            elif input_type["name"].val == "members":
                return types.List(types.Type())
        return types.Type()

    if not isinstance(input_type["name"], types.Const):
        return types.UnknownType()

    if isinstance(self_arg, types.ObjectType):
        key = input_type["name"].val
        property_types = self_arg.property_types()
        return property_types.get(key, types.Invalid())

    return types.Invalid()


@weave_class(weave_type=types.Type)
class Object:
    # Little hack, storage._get_ref expects to be able to check whether
    # any object hasattr('_ref') including nodes. Set it here so that
    # our __getattr__ op method doesn't handle that check.
    _ref = None

    # ipython tries to figure out if we have implemented a __getattr__
    # by checking for this attribute. But the weave.op() decorator makes
    # __getattr__ behave oddly, its now a lazy getattr that will always return
    # something. So add the attribute here to tell ipython that yes we do
    # have a __getattr__. This fixes Node._ipython_display()_ not getting fired.
    _ipython_canary_method_should_not_exist_ = None

    # Needed for storage.to_python hacks. Remove after those hacks are fixed.
    # TODO: fix
    to_pylist = None
    as_py = None

    # name is needed here since the decorator will rename to 'type-__getattr__'
    @op(name="Object-__getattr__", output_type=getattr_output_type)
    def __getattr__(self, name: str):
        return getattr(self, name)

    # TODO: figure out how this conflicts with the above __getattr__ op
    # particularly for lists
    def __getitem__(self, name: str):
        return self.__getattr__(name)
