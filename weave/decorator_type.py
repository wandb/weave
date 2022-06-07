import dataclasses

from . import weave_types as types
from . import infer_types
from . import decorator_class

_py_type = type


def type(__override_name: str = None):
    def wrap(target):
        dc = dataclasses.dataclass(target)
        fields = dataclasses.fields(dc)
        target_name = target.__name__
        if __override_name is not None:
            target_name = __override_name

        TargetType = _py_type(f"{target_name}Type", (types.ObjectType,), {})
        TargetType.name = target_name
        TargetType.instance_classes = target
        TargetType.instance_class = target
        TargetType.NodeMethodsClass = dc

        property_types = {
            field.name: infer_types.python_type_to_type(field.type) for field in fields
        }

        # If there are any variable type properties, make them variable
        # in the type we are creating.
        for name, prop_type in property_types.items():
            prop_type_vars = prop_type.type_vars
            if callable(prop_type_vars):
                prop_type_vars = prop_type_vars()
            if len(prop_type_vars):
                setattr(TargetType, name, prop_type)
                setattr(TargetType, "__annotations__", {})
                TargetType.__dict__["__annotations__"][name] = types.Type

        def property_types_method(self):
            return property_types

        TargetType.property_types = property_types_method
        TargetType = dataclasses.dataclass(TargetType)

        dc.WeaveType = TargetType
        decorator_class.weave_class(weave_type=TargetType)(dc)
        return dc

    return wrap
