from ..api import mutation, op, weave_class
from .. import weave_types as types


def getattr_output_type(input_type):
    key = input_type["name"].val
    property_types = input_type["self"].property_types()
    return property_types.get(key, types.Invalid())


@weave_class(weave_type=types.ObjectType)
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

    @mutation
    def obj_settattr(self, attr, v):
        setattr(self, attr, v)
        return self

    @op(setter=obj_settattr, output_type=getattr_output_type)
    def __getattr__(self, name: str):
        return getattr(self, name)
