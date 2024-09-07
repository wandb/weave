from weave.legacy.weave import weave_internal
from weave.legacy.weave import weave_types as types


# TODO: Consider if this should accept a *args, **kwargs?
def make(cls, kwargs={}):
    args = {types.to_weavejs_typekey(k): v for k, v in kwargs.items()}
    args["name"] = weave_internal.make_const_node(types.String(), cls.class_type_name())
    # TODO: Should we define this Op as a native Python op?
    return weave_internal.make_output_node(types.TypeType(), "type-__newType__", args)


types.Type._make = make  # type: ignore
