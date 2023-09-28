import contextlib
import contextvars
import dataclasses
import inspect
import typing
import black


from . import graph, registry_mem, codifiable_value_mixin, storage, weave_types


# User-facing Apis
def object_to_code(obj: typing.Any) -> str:
    raw_code = object_to_code_no_format(obj)
    formatted_code = black.format_str(raw_code, mode=black.FileMode())
    return formatted_code


def load(d: dict) -> typing.Any:
    return storage.from_python(d)


# Internal Apis
def object_to_code_no_format(obj: typing.Any) -> str:
    for method in [
        _try_otc_using_codifiable_mixin,  # TODO: Refactor this in followup to use duck typing.
        _try_otc_using_primitives,
        # _try_otc_using_type,  # I am pretty sure this is fragile. Skipping for now.
        _try_otc_using_nodes,
        _try_otc_using_dataclasses,
    ]:
        try:
            code = method(obj)
            if code is not None:
                return code
        except Exception as e:
            pass
            # print(e)

    # Try to use the object's storage representation:
    return _otc_using_storage_fallback(obj)


_var_node_frame: contextvars.ContextVar[
    typing.Optional[list[str]]
] = contextvars.ContextVar("var_node_frame", default=None)


@contextlib.contextmanager
def additional_var_nodes(names: list[str]) -> typing.Generator[None, None, None]:
    current_frame = _var_node_frame.get()
    if current_frame is None:
        current_frame = []
    new_frame = current_frame + names
    token = _var_node_frame.set(new_frame)
    yield
    _var_node_frame.reset(token)


def lambda_wrapped_object_to_code_no_format(
    obj: typing.Any, new_lambda_vars: list[str]
) -> str:
    if len(new_lambda_vars) == 0:
        return object_to_code_no_format(obj)
    else:
        with additional_var_nodes(new_lambda_vars):
            return (
                f"lambda {', '.join(new_lambda_vars)}: {object_to_code_no_format(obj)}"
            )


# Private Apis
def _try_otc_using_codifiable_mixin(obj: typing.Any) -> typing.Optional[str]:
    # TODO:
    #  * Make mixin a protocol.
    #  * Do this for Plot, Group, and Table.
    if isinstance(obj, codifiable_value_mixin.CodifiableValueMixin):
        return obj.to_code()
    return None


# def load_type(type_name: str, d: dict):
#     obj_type_cls = weave_types.type_name_to_type(type_name)
#     if obj_type_cls is None:
#         raise ValueError(f"Unknown type name: {type_name}")
#     return obj_type_cls().instance_from_dict(d)


# def _try_otc_using_type(obj: typing.Any) -> typing.Optional[str]:
#     # This is unlikely to work for many objects since many types will need params.
#     obj_type = weave_types.TypeRegistry.type_of(obj)
#     if obj_type is not None:
#         # check instantiation by name
#         assert weave_types.type_name_to_type(obj_type.name)() == obj_type
#         d = obj_type.instance_to_dict(obj)
#         obj_type_name = obj_type.name
#         return f"""weave.codify.load_type({obj_type_name}, {d})"""
#     return None


def _try_otc_using_primitives(obj: typing.Any) -> typing.Optional[str]:
    if isinstance(obj, (int, float, str, bool, type(None))):
        return repr(obj)
    elif isinstance(obj, list):
        return f"""[{", ".join(object_to_code_no_format(x) for x in obj)}]"""
    elif isinstance(obj, tuple):
        return f"""({", ".join(object_to_code_no_format(x) for x in obj)},)"""
    elif isinstance(obj, dict):
        return f"""{{{", ".join(f"{object_to_code_no_format(k)}: {object_to_code_no_format(v)}" for k, v in obj.items())}}}"""
    return None


def _try_otc_using_nodes(obj: typing.Any) -> typing.Optional[str]:
    if not isinstance(obj, graph.Node):
        return None

    return _node_to_code(obj)


def _try_otc_using_dataclasses(obj: typing.Any) -> typing.Optional[str]:
    if not dataclasses.is_dataclass(obj):
        return None

    class_type = type(obj)
    if class_type.__module__.startswith("weave.decorator_type") and issubclass(
        class_type, weave_types.Type
    ):
        qualified_classpath = "weave.weave_types"
        qualified_classname = f"type_name_to_type('{class_type.name}')"
    else:
        qualified_classpath = _module_name_corrections(class_type.__module__)
        qualified_classname = class_type.__name__

    if not qualified_classpath.startswith("weave."):
        return None

    fields = dataclasses.fields(obj)
    fields_to_use = {}

    allowed_init_params = inspect.signature(class_type.__init__).parameters.keys()

    for f in fields:
        if f.init:
            field_name = f.name
            if field_name in allowed_init_params:
                obj_val = getattr(obj, field_name)
                if f.default is not dataclasses.MISSING and _equality_helper(
                    obj_val, f.default
                ):
                    continue
                if f.default_factory is not dataclasses.MISSING and _equality_helper(
                    obj_val, f.default_factory()
                ):
                    continue
                fields_to_use[field_name] = obj_val

    res = f"""{qualified_classpath}.{qualified_classname}({", ".join(f"{k}={object_to_code_no_format(v)}" for k, v in fields_to_use.items())})"""
    return res


def _otc_using_storage_fallback(obj: typing.Any) -> str:
    return f"""weave.codify.load({storage.to_python(obj)})"""


# Helpers


# Hack:
def _module_name_corrections(qualified_name: str) -> str:
    if qualified_name == "weave.ops_primitives.file_local":
        return "weave.ops"
    elif qualified_name.startswith("weave.decorator_class"):
        raise ValueError("Decorator classes are not supported.")
    elif qualified_name.startswith("weave.decorator_type"):
        raise ValueError("Decorator types are not supported.")
    return qualified_name


def _equality_helper(a: typing.Any, b: typing.Any) -> bool:
    if isinstance(a, graph.Node) and isinstance(b, graph.Node):
        if isinstance(a, graph.VoidNode) and isinstance(b, graph.VoidNode):
            return True
        # TODO: More node handing here?
        return False

    return a == b


def _type_to_code(t: weave_types.Type) -> str:
    return object_to_code_no_format(t)


def _node_to_code(node: graph.Node, wrap_const_node: bool = True) -> str:
    if isinstance(node, graph.VoidNode):
        return "weave.graph.VoidNode()"
    elif isinstance(node, graph.VarNode):
        current_frame = _var_node_frame.get()

        if current_frame is not None and node.name in current_frame:
            return node.name
        return f"weave.weave_internal.make_var_node({_type_to_code(node.type)}, '{node.name}')"
    elif isinstance(node, graph.ConstNode):
        if isinstance(node.type, weave_types.Function):
            vars = list(node.type.input_types.keys())
            return lambda_wrapped_object_to_code_no_format(node.val, vars)
        else:
            val_as_code = object_to_code_no_format(node.val)
            if wrap_const_node:
                return f"weave.weave_internal.const({val_as_code})"
            else:
                return val_as_code
    elif isinstance(node, graph.OutputNode):
        full_op_name = node.from_op.name
        prefix = ""
        inputs = list(node.from_op.inputs.values())

        if node.from_op.name == "dict":
            args = ",".join(
                [
                    key + "=" + _node_to_code(val, False)
                    for key, val in node.from_op.inputs.items()
                ]
            )
            if len(node.from_op.inputs) > 0:
                args += ","
            return f"weave.ops_primitives.dict.dict_({args})"
        elif node.from_op.name == "list":
            args = ",".join(
                [
                    key + "=" + _node_to_code(val, False)
                    for key, val in node.from_op.inputs.items()
                ]
            )
            if len(node.from_op.inputs) > 0:
                args += ","
            return f"weave.ops_primitives.list_.make_list({args})"

        is_root = len(inputs) == 0 or not isinstance(
            inputs[0], (graph.OutputNode, graph.VarNode)
        )

        if is_root:
            # In this case we need to find the qualified op name
            op_def = registry_mem.memory_registry.get_op(full_op_name)
            if op_def is None:
                raise ValueError(f"Unknown op name: {full_op_name}")
            op_name = op_def.raw_resolve_fn.__name__
            prefix = _module_name_corrections(op_def.raw_resolve_fn.__module__)
        else:
            op_name = full_op_name.split("-")[-1]
            prefix = _node_to_code(inputs[0])
            inputs = inputs[1:]

        params = ",".join([_node_to_code(n, False) for n in inputs])

        # Special syntax
        if op_name == "pick":
            return f"{prefix}[{params}]"

        if len(inputs) > 0:
            params += ","

        return f"{prefix}.{op_name}({params})"
    else:
        raise ValueError(f"Unknown node type: {node}")
