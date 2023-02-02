import typing
from ..api import op
from ..compile_domain import InputProvider, wb_gql_op_plugin
from .. import weave_types
from inspect import signature, Parameter
from . import wb_domain_types
import hashlib
from .. import errors

"""
This file contains utilities for constructing GQL ops (used by all the ops in
`ops_domain`). There are explicitly 4 functions:
    - `gql_prop_op`: used for getting properties of GQL objects
    - `gql_root_op`: used to start a query (much match to a query on the `Query`
      type)
    - `gql_direct_edge_op`: used to get a direct edge of a GQL object leading to
      another GQL object
        - Has an additional `is_many` arg to determine if the result is a single
          or many objects
    - `gql_connection_op`: used to get a connection of GQL objects (the standard
      edges/nodes pattern)

All but the prop_op have the ability to specify additional inputs and how to map
such inputs to a query param string.

Each of these leverage the underlying `wb_gql_op_plugin` to create an op. You
are always free to directly use `wb_gql_op_plugin` if you need to write custom
logic - these are just wrappers since these cases are so common. 

Please see `project_ops.py` for examples of all the above cases.
"""


def _make_alias(*args: str, prefix: str = "alias") -> str:
    inputs = "_".join([str(arg) for arg in args])
    digest = hashlib.md5(inputs.encode()).hexdigest()
    return f"{prefix}_{digest}"


def gql_prop_op(
    op_name: str,
    input_type: weave_types.Type,
    prop_name: str,
    output_type: weave_types.Type,
):
    first_arg_name = input_type.name

    def gql_property_getter_op_fn(**inputs):
        if isinstance(output_type, weave_types.Timestamp):
            return output_type.from_isostring(inputs[first_arg_name].gql[prop_name])
        return inputs[first_arg_name].gql[prop_name]

    sig = signature(gql_property_getter_op_fn)
    params = [Parameter(first_arg_name, Parameter.POSITIONAL_OR_KEYWORD)]
    sig = sig.replace(parameters=tuple(params))
    gql_property_getter_op_fn.__signature__ = sig  # type: ignore
    gql_property_getter_op_fn.sig = sig  # type: ignore

    return op(
        name=op_name,
        plugins=wb_gql_op_plugin(
            lambda inputs, inner: prop_name,
        ),
        input_type={first_arg_name: input_type},
        output_type=output_type,
    )(gql_property_getter_op_fn)


def _get_required_fragment(output_type: weave_types.Type):
    return (
        output_type.instance_class.REQUIRED_FRAGMENT  # type: ignore
        if output_type.instance_class is not None
        and hasattr(output_type.instance_class, "REQUIRED_FRAGMENT")
        else ""
    )


def gql_root_op(
    op_name: str,
    prop_name: str,
    output_type: weave_types.Type,
    additional_inputs_types: typing.Optional[dict[str, weave_types.Type]] = None,
    param_str_fn: typing.Optional[typing.Callable[[InputProvider], str]] = None,
):
    return gql_direct_edge_op(
        op_name,
        None,
        prop_name,
        output_type,
        additional_inputs_types,
        param_str_fn,
    )


def gql_direct_edge_op(
    op_name: str,
    input_type: typing.Optional[weave_types.Type],
    prop_name: str,
    output_type: weave_types.Type,
    additional_inputs_types: typing.Optional[dict[str, weave_types.Type]] = None,
    param_str_fn: typing.Optional[typing.Callable[[InputProvider], str]] = None,
    is_many: bool = False,
):
    is_root = input_type is None
    first_arg_name = "gql_obj" if input_type is None else input_type.name
    if not output_type.instance_class or isinstance(
        output_type.instance_class, wb_domain_types.GQLTypeMixin
    ):
        raise ValueError(
            f"output_type must be a GQLTypeMixin, got {output_type} instead"
        )

    def query_fn(inputs, inner):
        alias = ""
        param_str = ""
        if param_str_fn:
            param_str = param_str_fn(inputs)
            alias = f"{_make_alias(param_str, prefix=prop_name)}:"
            param_str = f"({param_str})"
        return f"""
            {alias} {prop_name}{param_str} {{
                {_get_required_fragment(output_type)}
                {inner}
            }}
        """

    additional_inputs_types = additional_inputs_types or {}
    if is_root:

        def gql_relationship_getter_op(**inputs):
            raise errors.WeaveGQLCompileError(
                f"{op_name} should not be executed directly. If you see this error, it is a bug in the Weave compiler."
            )

    else:

        def gql_relationship_getter_op(**inputs):
            gql_obj = inputs[first_arg_name]
            additional_inputs = {
                key: value for key, value in inputs.items() if key != first_arg_name
            }
            name = prop_name
            if param_str_fn:
                param_str = param_str_fn(InputProvider(additional_inputs))
                name = _make_alias(param_str, prefix=prop_name)
            if is_many:
                return [
                    output_type.instance_class.from_gql(item)
                    for item in gql_obj.gql[name]
                ]
            if gql_obj.gql == wb_domain_types.UntypedOpaqueDict.from_json_dict(None):
                return None
            gql_val = gql_obj.gql.get(name)
            if gql_val is None:
                return None
            return output_type.instance_class.from_gql(gql_val)

    sig = signature(gql_relationship_getter_op)
    base_params = (
        [Parameter(first_arg_name, Parameter.POSITIONAL_OR_KEYWORD)]
        if not is_root
        else []
    )
    new_params = [
        *base_params,
        *[
            Parameter(key, Parameter.POSITIONAL_OR_KEYWORD)
            for key in additional_inputs_types.keys()
        ],
    ]
    sig = sig.replace(parameters=tuple(new_params))
    gql_relationship_getter_op.__signature__ = sig  # type: ignore
    gql_relationship_getter_op.sig = sig  # type: ignore

    base_input_type = {first_arg_name: input_type} if not is_root else {}
    _output_type = output_type
    if is_many:
        _output_type = weave_types.List(output_type)
    gql_relationship_getter_op = op(
        name=op_name,
        plugins=wb_gql_op_plugin(query_fn, is_root),
        input_type={**base_input_type, **additional_inputs_types},
        output_type=_output_type,
    )(gql_relationship_getter_op)

    return gql_relationship_getter_op


def gql_connection_op(
    op_name: str,
    input_type: weave_types.Type,
    prop_name: str,
    output_type: weave_types.Type,
    additional_inputs_types: typing.Optional[dict[str, weave_types.Type]] = None,
    param_str_fn: typing.Optional[typing.Callable[[InputProvider], str]] = None,
):
    first_arg_name = "gql_obj" if input_type is None else input_type.name
    if not output_type.instance_class or isinstance(
        output_type.instance_class, wb_domain_types.GQLTypeMixin
    ):
        raise ValueError(
            f"output_type must be a GQLTypeMixin, got {output_type} instead"
        )

    def query_fn(inputs, inner):
        alias = ""
        param_str = ""
        if param_str_fn:
            param_str = param_str_fn(inputs)
            alias = f"{_make_alias(param_str, prefix=prop_name)}:"
            param_str = f"({param_str})"
        return f"""
            {alias} {prop_name}{param_str} {{
                edges {{
                    node {{
                        {_get_required_fragment(output_type)}
                        {inner}
                    }}
                }}
            }}
        """

    additional_inputs_types = additional_inputs_types or {}

    def gql_connection_walker_op(**inputs):
        gql_obj = inputs[first_arg_name]
        additional_inputs = {
            key: value for key, value in inputs.items() if key != first_arg_name
        }
        name = prop_name
        if param_str_fn:
            param_str = param_str_fn(InputProvider(additional_inputs))
            name = _make_alias(param_str, prefix=prop_name)
        # If we have a None argument, return an empty list.
        if gql_obj.gql == wb_domain_types.UntypedOpaqueDict.from_json_dict(None):
            return []
        return [
            output_type.instance_class.from_gql(edge["node"])
            for edge in gql_obj.gql[name]["edges"]
        ]

    sig = signature(gql_connection_walker_op)
    new_params = [
        Parameter(first_arg_name, Parameter.POSITIONAL_OR_KEYWORD),
        *[
            Parameter(key, Parameter.POSITIONAL_OR_KEYWORD)
            for key in additional_inputs_types.keys()
        ],
    ]
    sig = sig.replace(parameters=tuple(new_params))
    gql_connection_walker_op.__signature__ = sig  # type: ignore
    gql_connection_walker_op.sig = sig  # type: ignore
    gql_connection_walker_op = op(
        name=op_name,
        plugins=wb_gql_op_plugin(query_fn),
        input_type={first_arg_name: input_type, **additional_inputs_types},
        output_type=weave_types.List(output_type),
    )(gql_connection_walker_op)

    return gql_connection_walker_op
