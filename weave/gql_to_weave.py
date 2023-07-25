from graphql import (
    parse,
    get_operation_root_type,
    GraphQLObjectType,
    GraphQLList,
    GraphQLNonNull,
    GraphQLInterfaceType,
    FieldNode,
    OperationDefinitionNode,
)
import graphql
import pathlib
import typing

from . import errors
from . import weave_types as types


_GQL_SCHEMA: typing.Optional[graphql.GraphQLSchema] = None


def get_outermost_alias(query_str: str) -> str:
    gql_doc = graphql.language.parse(f"query innerquery {{ {query_str} }}")
    root_operation = gql_doc.definitions[0]
    if not isinstance(root_operation, graphql.language.ast.OperationDefinitionNode):
        raise errors.WeaveInternalError("Only operation definitions are supported.")
    if len(root_operation.selection_set.selections) != 1:
        # NOTE: if we ever need a root op to have multiple root selections, we
        # can easily loosen this restriction and just return a list of aliases
        raise errors.WeaveInternalError("Only one root selection is supported")
    inner_selection = root_operation.selection_set.selections[0]
    if not isinstance(inner_selection, graphql.language.ast.FieldNode):
        raise errors.WeaveInternalError("Only field selections are supported")
    if inner_selection.alias is not None:
        return inner_selection.alias.value
    return inner_selection.name.value


def get_gql_schema() -> graphql.GraphQLSchema:
    global _GQL_SCHEMA
    if _GQL_SCHEMA is None:
        with open(pathlib.Path(__file__).parent / "schema.gql") as f:
            schema_str = f.read()

        _GQL_SCHEMA = graphql.build_schema(schema_str)
    return _GQL_SCHEMA


def gql_type_to_weave_type(
    gql_type: graphql.GraphQLType,
    selection_set: typing.Optional[graphql.SelectionSetNode],
) -> types.Type:
    if (
        isinstance(gql_type, (GraphQLObjectType, GraphQLInterfaceType))
        and selection_set
    ):
        property_types: dict[str, types.Type] = {}
        for selection in selection_set.selections:
            if not isinstance(selection, FieldNode):
                raise ValueError(
                    f"Selections must be fields, got {selection.__class__.__name__}"
                )
            key = selection.alias.value if selection.alias else selection.name.value
            if key == "__typename":
                # __typename does not appear explicitly in the schema, but all types have it
                # it just returns a string, so treat that case here.
                property_types[key] = types.String()
            else:
                property_types[key] = gql_type_to_weave_type(
                    gql_type.fields[selection.name.value].type, selection.selection_set
                )
        return types.TypedDict(property_types)

    elif isinstance(gql_type, GraphQLList):
        return types.List(gql_type_to_weave_type(gql_type.of_type, selection_set))
    elif isinstance(gql_type, GraphQLNonNull):
        return types.non_none(gql_type_to_weave_type(gql_type.of_type, selection_set))
    elif isinstance(gql_type, graphql.GraphQLUnionType):
        return types.union(
            *[gql_type_to_weave_type(t, selection_set) for t in gql_type.types]
        )
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
            schema = get_gql_schema()
            root_operation_type = get_operation_root_type(schema, definition)
            return gql_type_to_weave_type(root_operation_type, definition.selection_set)
    raise ValueError("No operation found in query")
