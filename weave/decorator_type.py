import dataclasses

from . import types
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

        def __init__(self):
            for field in fields:
                setattr(self, field.name)

        # TargetType.__init__ = __init__

        def property_types(self):
            return {
                field.name: infer_types.python_type_to_type(field.type)
                for field in fields
            }

        TargetType.property_types = property_types
        dc.WeaveType = TargetType
        decorator_class.weave_class(weave_type=TargetType)(dc)
        return dc

    return wrap
