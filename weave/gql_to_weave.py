from graphql import (
    parse,
    get_operation_root_type,
    GraphQLObjectType,
    GraphQLList,
    GraphQLNonNull,
    FieldNode,
    OperationDefinitionNode,
)
import graphql
import pathlib
import typing
from . import weave_types as types

with open(pathlib.Path(__file__).parent / "schema.gql") as f:
    schema_str = f.read()

GQL_SCHEMA = graphql.build_schema(schema_str)


def gql_type_to_weave_type(
    gql_type: graphql.GraphQLType,
    selection_set: typing.Optional[graphql.SelectionSetNode],
) -> types.Type:
    if isinstance(gql_type, GraphQLObjectType) and selection_set:
        property_types: dict[str, types.Type] = {}
        for selection in selection_set.selections:
            if not isinstance(selection, FieldNode):
                raise ValueError(
                    f"Selections must be fields, got {selection.__class__.__name__}"
                )
            property_types[selection.name.value] = gql_type_to_weave_type(
                gql_type.fields[selection.name.value].type, selection.selection_set
            )
        return types.TypedDict(property_types)

    elif isinstance(gql_type, GraphQLList):
        return types.List(
            gql_type_to_weave_type(gql_type.of_type, None)
        )  # None because list items don't have a selection set
    elif isinstance(gql_type, GraphQLNonNull):
        return types.non_none(gql_type_to_weave_type(gql_type.of_type, selection_set))
    elif isinstance(gql_type, graphql.GraphQLScalarType):
        t: types.Type
        if gql_type.name in [
            "String",
            "ID",
            "JSONString",
        ]:
            t = types.String()
        elif gql_type.name in ["Int", "Int64"]:
            t = types.Int()
        elif gql_type.name == "Float":
            t = types.Float()
        elif gql_type.name == "Boolean":
            t = types.Boolean()
        elif gql_type.name == "JSON":
            t = types.Dict()
        elif gql_type.name == "DateTime":
            t = types.Timestamp()
        elif gql_type.name == "Duration":
            t = types.TimeDelta()
        else:
            raise ValueError(f"Unknown scalar type {gql_type.name}")

        return types.optional(t)

    raise ValueError(f"Unknown type {gql_type}")


def get_query_weave_type(query: str) -> types.Type:
    document = parse(query)
    for definition in document.definitions:
        if isinstance(definition, OperationDefinitionNode):
            root_operation_type = get_operation_root_type(GQL_SCHEMA, definition)
            return gql_type_to_weave_type(root_operation_type, definition.selection_set)
    raise ValueError("No operation found in query")
