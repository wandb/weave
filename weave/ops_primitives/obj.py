from ..api import op, weave_class
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

    @op(output_type=getattr_output_type)
    def __getattr__(self, name: str):
        return getattr(self, name)
