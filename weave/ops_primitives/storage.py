from ..api import op, mutation
from .. import weave_types as types


def op_get_return_type(uri):
    from .. import uris

    return uris.WeaveURI.parse(uri).to_ref().type


def op_get_return_type_from_inputs(inputs):
    return op_get_return_type(inputs["uri"].val)


@op(name="getReturnType", input_type={"uri": types.String()}, output_type=types.Type())
def get_returntype(uri):
    return op_get_return_type(uri)


# Hmm... This returns the same obj, not a ref anymore
# TODO: is this what we want?
@op(
    name="save",
    input_type={"obj": types.Any(), "name": types.String()},
    output_type=lambda input_types: input_types["obj"],
)
def save(obj, name):
    from . import storage

    ref = storage.save(obj, name=name)
    return ref.obj


@mutation
def _save(name, obj):
    from . import storage
    from .. import uris

    obj_uri = uris.WeaveURI.parse(name)

    storage.save(obj, name=obj_uri.full_name)


@op(
    pure=False,
    setter=_save,
    name="get",
    input_type={"uri": types.String()},
    output_type=op_get_return_type_from_inputs,
)
def get(uri):
    from . import storage

    return storage.get(uri)
