import inspect
import typing
import dataclasses

from . import weave_types as types
from . import infer_types
from . import decorator_class
from . import errors
from . import decorator_op

_py_type = type


def type(
    __override_name: typing.Optional[str] = None,
    __is_simple: bool = False,
    __init: typing.Optional[bool] = None,
    __mixins: typing.Optional[list[typing.Type]] = None,
):
    def wrap(target):
        init = False
        if __init is not None:
            init = __init
        else:
            init = getattr(target.__bases__[0], "__init", True)
        target.__init = init
        dc = dataclasses.dataclass(target, init=init)
        fields = dataclasses.fields(dc)
        target_name = target.__name__
        if __override_name is not None:
            target_name = __override_name

        base_type = types.ObjectType
        if target.__bases__:
            # Add the first base classes as the type base.
            # TODO: should we add all bases?
            target_base0 = target.__bases__[0]
            if hasattr(target_base0, "WeaveType"):
                base_type = target_base0.WeaveType

        if __is_simple:
            bases = (
                base_type,
                types._PlainStringNamedType,
            )
        else:
            bases = (base_type,)

        if __mixins is not None:
            bases = tuple(__mixins) + bases

        TargetType = _py_type(f"{target_name}Type", bases, {})
        TargetType.name = target_name
        TargetType.instance_classes = target
        TargetType.instance_class = target

        type_vars: dict[str, types.Type] = {}
        static_property_types: dict[str, types.Type] = {}
        for field in fields:
            if isinstance(field.type, typing.TypeVar):
                # This is a Python type variable
                type_vars[field.name] = types.Any()
            else:
                try:
                    weave_type = infer_types.python_type_to_type(field.type)
                except TypeError:
                    # hmmm... Exception rewriting. Am I OK with this? Could be overly aggressive.
                    # TODO: decide if we should do this
                    raise errors.WeaveDefinitionError(
                        f"{target}.{field.name} is not a valid python type (a class or type)"
                    )

                if types.type_is_variable(weave_type):
                    # this is a Weave type with a type variable in it
                    type_vars[field.name] = weave_type
                else:
                    static_property_types[field.name] = weave_type

        if type_vars:
            setattr(TargetType, "__annotations__", {})
        for name, default_type in type_vars.items():
            setattr(TargetType, name, default_type)
            TargetType.__dict__["__annotations__"][name] = types.Type

        def property_types_method(self):
            property_types = {}
            for name in type_vars:
                property_types[name] = getattr(self, name)
            for name, prop_type in static_property_types.items():
                property_types[name] = prop_type
            return property_types

        TargetType.property_types = property_types_method

        if not type_vars:
            # workaround rich bug. dataclasses __repr__ doesn't print if the dataclass has no
            # fields. Insert our own __repr__ in that case so rich doesn't try to do its
            # special dataclass repr.
            TargetType.__repr__ = lambda self: f"{self.__class__.__name__}()"

        TargetType = dataclasses.dataclass(frozen=True)(TargetType)

        dc.WeaveType = TargetType
        decorator_class.weave_class(weave_type=TargetType)(dc)

        # constructor op for this type. due to a circular dependency with ArrowWeave* types, we
        # define the vectorized constructor ops in vectorize.py instead of here
        @decorator_op.op(
            name=f"objectConstructor-_new_{target_name.replace('-', '_')}",
            input_type={
                field.name: static_property_types.get(field.name, None)
                or type_vars[field.name]
                for field in fields
            },
            output_type=TargetType(),
            render_info={"type": "function"},
        )
        def constructor(**attributes):
            return dc(
                **{field.name: attributes[field.name] for field in fields if field.init}
            )

        dc.constructor = constructor

        return dc

    return wrap
