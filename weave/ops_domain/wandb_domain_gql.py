import typing
from ..api import op
from ..gql_op_plugin import wb_gql_op_plugin
from .. import weave_types
from inspect import signature, Parameter
from . import wb_domain_types
from .. import errors
from ..ops_arrow import ArrowWeaveListType, ArrowWeaveList
from ..decorator_arrow_op import arrow_op
from .. import op_def
from .. import partial_object
from ..input_provider import InputProvider
import hashlib

from .. import gql_op_plugin


from ..input_provider import InputProvider


import pyarrow as pa

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


ParamStrFn = typing.Callable[[InputProvider], str]


def _make_alias(*args: str, prefix: str = "alias") -> str:
    inputs = "_".join([str(arg) for arg in args])
    digest = hashlib.md5(inputs.encode()).hexdigest()
    return f"{prefix}_{digest}"


def _param_str(inputs: InputProvider, param_str_fn: typing.Optional[ParamStrFn]) -> str:
    param_str = ""
    if param_str_fn:
        param_str = param_str_fn(inputs)
    return param_str


def _alias(
    inputs: InputProvider,
    param_str_fn: typing.Optional[ParamStrFn],
    prop_name: str,
) -> str:
    alias = ""
    param_str = _param_str(inputs, param_str_fn)
    if param_str_fn:
        alias = f"{_make_alias(param_str, prefix=prop_name)}"
    return alias


def register_vectorized_gql_prop_op(
    scalar_op: op_def.OpDef, prop_name: str, scalar_output_type: weave_types.Type
) -> None:
    op_args = scalar_op.input_type

    first_arg_name: str
    scalar_input_type: weave_types.Type
    scalar_op_name = scalar_op.name
    first_arg_name = next(iter(op_args.to_dict()))
    original_scalar_input_type = op_args.initial_arg_types[first_arg_name]

    # require that the desired key be present on the object type
    assert isinstance(
        original_scalar_input_type, partial_object.PartialObjectTypeGeneratorType
    )
    scalar_input_type = original_scalar_input_type.with_keys(
        {prop_name: scalar_output_type}
    )

    vectorized_op_name = "ArrowWeaveList" + scalar_op_name
    arrow_input_type = {first_arg_name: ArrowWeaveListType(scalar_input_type)}
    arrow_output_type = ArrowWeaveListType(scalar_output_type)

    def vectorized_gql_property_getter_op_fn(**inputs):
        self = typing.cast(ArrowWeaveList, inputs[first_arg_name])
        object_type = typing.cast(partial_object.PartialObjectType, self.object_type)
        return ArrowWeaveList(
            # keep things dictionary encoded
            pa.DictionaryArray.from_arrays(
                self._arrow_data.indices, self._arrow_data.dictionary.field(prop_name)
            ),
            object_type.keys[prop_name],
            self._artifact,
        )

    vectorized_gql_property_getter_op_fn.__signature__ = (  # type: ignore
        scalar_op.raw_resolve_fn.__signature__  # type: ignore
    )

    vectorized_gql_property_getter_op_fn.sig = scalar_op.raw_resolve_fn.sig  # type: ignore

    arrow_op(
        name=vectorized_op_name,
        input_type=arrow_input_type,
        output_type=arrow_output_type,
        plugins=scalar_op.plugins,
    )(vectorized_gql_property_getter_op_fn)


def gql_prop_op(
    op_name: str,
    input_type: weave_types.Type,
    prop_name: str,
    output_type: weave_types.Type,
    hidden: bool = False,
):
    first_arg_name = input_type.name

    def gql_property_getter_op_fn(**inputs):
        return inputs[first_arg_name][prop_name]

    sig = signature(gql_property_getter_op_fn)
    params = [Parameter(first_arg_name, Parameter.POSITIONAL_OR_KEYWORD)]
    sig = sig.replace(parameters=tuple(params))
    gql_property_getter_op_fn.__signature__ = sig  # type: ignore
    gql_property_getter_op_fn.sig = sig  # type: ignore

    scalar_op = op(
        name=op_name,
        plugins=wb_gql_op_plugin(
            lambda inputs, inner: prop_name,
        ),
        input_type={first_arg_name: input_type},
        output_type=output_type,
        hidden=hidden,
    )(gql_property_getter_op_fn)

    # side effect: register an arrow-vectorized version of the op
    register_vectorized_gql_prop_op(scalar_op, prop_name, output_type)
    return scalar_op


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
    param_str_fn: typing.Optional[ParamStrFn] = None,
    is_many: bool = False,
):
    is_root = input_type is None
    first_arg_name = "gql_obj" if input_type is None else input_type.name
    if not output_type.instance_class or isinstance(
        output_type.instance_class, wb_domain_types.PartialObject
    ):
        raise ValueError(
            f"output_type must be a GQLTypeMixin, got {output_type} instead"
        )

    def query_fn(inputs, inner):
        alias = ""
        param_str = ""
        if param_str_fn is not None:
            param_str = _param_str(inputs, param_str_fn)
            alias = _alias(inputs, param_str_fn, prop_name)
            param_str = f"({param_str})"
            alias = f"{alias}:"
        return f"""
            {alias} {prop_name}{param_str} {{
                {_get_required_fragment(output_type)}
                {inner}
            }}
        """

    def key_fn(
        input_provider: InputProvider, self_type: weave_types.Type
    ) -> weave_types.Type:
        alias = _alias(input_provider, param_str_fn, prop_name)
        key = alias if alias != "" else prop_name

        ret_type = output_type
        if isinstance(self_type, partial_object.PartialObjectType):
            keys = self_type.keys
            assert isinstance(
                output_type, partial_object.PartialObjectTypeGeneratorType
            )
            new_keys = keys[key]
            if is_many:
                new_keys = typing.cast(weave_types.List, new_keys).object_type
            new_keys = typing.cast(weave_types.TypedDict, new_keys)
            ret_type = output_type.with_keys(new_keys.property_types)

        if is_many:
            ret_type = weave_types.List(ret_type)

        return ret_type

    additional_inputs_types = additional_inputs_types or {}
    if is_root:

        def gql_relationship_getter_op(**inputs):
            raise errors.WeaveGQLCompileError(
                f"{op_name} should not be executed directly. If you see this error, it is a bug in the Weave compiler."
            )

    else:

        def gql_relationship_getter_op(**inputs):
            gql_obj: partial_object.PartialObject = inputs[first_arg_name]
            additional_inputs = {
                key: value for key, value in inputs.items() if key != first_arg_name
            }
            name = prop_name
            if param_str_fn:
                param_str = param_str_fn(InputProvider(additional_inputs))
                name = _make_alias(param_str, prefix=prop_name)

            assert issubclass(output_type.instance_class, partial_object.PartialObject)

            if is_many:
                return [
                    output_type.instance_class.from_keys(item) for item in gql_obj[name]
                ]
            if (
                len(gql_obj.keys) is None
            ):  # == wb_domain_types.UntypedOpaqueDict.from_json_dict(None):
                return None
            gql_val = gql_obj[name]
            if gql_val is None:
                return None
            return output_type.instance_class.from_keys(gql_val)

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
        plugins=wb_gql_op_plugin(query_fn, is_root, None, key_fn),
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
        output_type.instance_class, wb_domain_types.PartialObject
    ):
        raise ValueError(
            f"output_type must be a GQLTypeMixin, got {output_type} instead"
        )

    def query_fn(inputs, inner):
        alias = ""
        param_str = ""
        if param_str_fn:
            alias = _alias(inputs, param_str_fn, prop_name)
            param_str = _param_str(inputs, param_str_fn)
            param_str = f"({param_str})"
            alias = alias + ":"

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

    def key_fn(
        input_provider: InputProvider, self_type: weave_types.Type
    ) -> weave_types.Type:
        alias = _alias(input_provider, param_str_fn, prop_name)
        key = alias if alias != "" else prop_name

        if isinstance(self_type, partial_object.PartialObjectType):
            keys = self_type.keys
            assert isinstance(
                output_type, partial_object.PartialObjectTypeGeneratorType
            )
            new_keys = typing.cast(
                weave_types.TypedDict,
                typing.cast(
                    weave_types.TypedDict,
                    typing.cast(
                        weave_types.List,
                        typing.cast(weave_types.TypedDict, keys[key]).property_types[
                            "edges"
                        ],
                    ).object_type,
                ).property_types["node"],
            )
            return weave_types.List(output_type.with_keys(new_keys.property_types))

        return weave_types.List(output_type)

    additional_inputs_types = additional_inputs_types or {}

    def gql_connection_walker_op(**inputs):
        gql_obj: partial_object.PartialObject = inputs[first_arg_name]
        additional_inputs = {
            key: value for key, value in inputs.items() if key != first_arg_name
        }
        name = prop_name
        if param_str_fn:
            param_str = param_str_fn(InputProvider(additional_inputs))
            name = _make_alias(param_str, prefix=prop_name)
        # If we have a None argument, return an empty list.
        if (
            gql_obj.keys == []
        ):  #  == wb_domain_types.UntypedOpaqueDict.from_json_dict(None):
            return []
        return [
            output_type.instance_class.from_keys(edge["node"])
            for edge in gql_obj[name]["edges"]
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
        plugins=wb_gql_op_plugin(query_fn, False, None, key_fn),
        input_type={first_arg_name: input_type, **additional_inputs_types},
        output_type=weave_types.List(output_type),
    )(gql_connection_walker_op)

    return gql_connection_walker_op


def make_root_op_gql_op_output_type(
    prop_name: str,
    param_str_fn: ParamStrFn,
    output_type: partial_object.PartialObjectTypeGeneratorType,
    use_alias: bool = False,
) -> gql_op_plugin.GQLOutputTypeFn:
    """Creates a GQLOutputTypeFn for a root op that returns a list of objects with keys."""

    def _root_op_gql_op_output_type(
        inputs: InputProvider, input_type: weave_types.Type
    ) -> weave_types.Type:
        key = (
            prop_name
            if not use_alias
            else _alias(
                inputs,
                param_str_fn,
                prop_name,
            )
        )

        key_type: weave_types.Type = typing.cast(weave_types.TypedDict, input_type)
        keys = ["instance", key, "edges", "node"]
        for key in keys:
            if isinstance(key_type, weave_types.List):
                key_type = key_type.object_type
            if isinstance(key_type, weave_types.TypedDict):
                key_type = key_type.property_types[key]

        object_type = output_type.with_keys(
            typing.cast(weave_types.TypedDict, key_type).property_types
        )
        return weave_types.List(object_type)

    return _root_op_gql_op_output_type
