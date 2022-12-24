"""
This file contains helper functions for working with ops that accept
lambda functions as params (filter, sort, groupby, map, join, etc..). We probably
should store this info on the opdef itself - however to keep things simple for now
we just store it here.
"""

import typing

from . import weave_types as types

if typing.TYPE_CHECKING:
    from . import op_def as OpDef


def _map_each_function_type(
    input_types: dict[str, types.Type], arr_key: str = "key"
) -> types.Function:
    if types.List().assign_type(input_types[arr_key]):
        return _map_each_function_type(
            {arr_key: typing.cast(types.List, input_types[arr_key]).object_type}
        )
    return types.Function({"row": input_types[arr_key]}, types.Any())


class LambdaOpDefHelper:
    @staticmethod
    def applies_to_op(op_def: "OpDef.OpDef") -> bool:
        raise NotImplementedError()

    @staticmethod
    def input_types_to_lambda_input_types(
        input_types: typing.Dict[str, types.Type]
    ) -> typing.Dict[str, types.Type]:
        raise NotImplementedError()


class GeneralListOpDefHelper(LambdaOpDefHelper):
    @staticmethod
    def applies_to_op(op_def: "OpDef.OpDef") -> bool:
        return (
            op_def.name == "map"
            or op_def.name == "filter"
            or op_def.name == "groupby"
            or op_def.name == "sort"
        )

    @staticmethod
    def input_types_to_lambda_input_types(
        input_types: typing.Dict[str, types.Type]
    ) -> typing.Dict[str, types.Type]:
        return {
            "row": input_types["arr"].object_type,
            # Weave0 has "index"... seems like this is missing in Weave1
            # "index": types.Int(),
        }


class ListMapEachOpDefHelper(LambdaOpDefHelper):
    @staticmethod
    def applies_to_op(op_def: "OpDef.OpDef") -> bool:
        return op_def.name == "mapEach"

    @staticmethod
    def input_types_to_lambda_input_types(
        input_types: typing.Dict[str, types.Type]
    ) -> typing.Dict[str, types.Type]:
        return _map_each_function_type(input_types).input_types


class GeneralArrowListOpDefHelper(LambdaOpDefHelper):
    @staticmethod
    def applies_to_op(op_def: "OpDef.OpDef") -> bool:
        return (
            op_def.name == "ArrowWeaveList-map"
            or op_def.name == "ArrowWeaveList-filter"
            or op_def.name == "ArrowWeaveList-groupby"
            or op_def.name == "ArrowWeaveList-sort"
        )

    @staticmethod
    def input_types_to_lambda_input_types(
        input_types: typing.Dict[str, types.Type]
    ) -> typing.Dict[str, types.Type]:
        return {
            "row": input_types["self"].object_type,
            # Weave0 has "index"... seems like this is missing in Weave1
            # "index": types.Int(),
        }


class ArrowListMapEachOpDefHelper(LambdaOpDefHelper):
    @staticmethod
    def applies_to_op(op_def: "OpDef.OpDef") -> bool:
        return op_def.name == "ArrowWeaveList-mapEach"

    @staticmethod
    def input_types_to_lambda_input_types(
        input_types: typing.Dict[str, types.Type]
    ) -> typing.Dict[str, types.Type]:
        return _map_each_function_type(input_types, "self").input_types


class GroupedArrowTableOpDefHelper(LambdaOpDefHelper):
    @staticmethod
    def applies_to_op(op_def: "OpDef.OpDef") -> bool:
        return (
            op_def.name == "ArrowTableGroupBy-map"
            or op_def.name == "ArrowTableGroupBy-sort"
        )

    @staticmethod
    def input_types_to_lambda_input_types(
        input_types: typing.Dict[str, types.Type]
    ) -> typing.Dict[str, types.Type]:
        return {
            "row": input_types["self"].object_type,
            # Weave0 has "index"... seems like this is missing in Weave1
            # "index": types.Int(),
        }
