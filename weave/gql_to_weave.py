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

with open(pathlib.Path(__file__).parent / "schema.gql") as f:
    schema_str = f.read()

GQL_SCHEMA = graphql.build_schema(schema_str)


def get_nested_return_type(
    return_type: graphql.GraphQLType, selection_set: graphql.SelectionSetNode
) -> graphql.GraphQLType:
    for selection in selection_set.selections:
        if isinstance(selection, FieldNode):
            if isinstance(return_type, (GraphQLList, GraphQLNonNull)):
                return_type = return_type.of_type

            if isinstance(return_type, GraphQLObjectType):
                field = return_type.fields.get(selection.name.value)
                if not field:
                    raise ValueError(f"Unknown field {selection.name.value}")
                return_type = field.type

            if selection.selection_set:
                return_type = get_nested_return_type(
                    return_type, selection.selection_set
                )

    return return_type


def get_return_type(schema: graphql.GraphQLSchema, query: str) -> graphql.GraphQLType:
    document = parse(query)
    for definition in document.definitions:
        if isinstance(definition, OperationDefinitionNode):
            root_operation_type = get_operation_root_type(schema, definition)
            return get_nested_return_type(root_operation_type, definition.selection_set)
    raise ValueError("No operation found in query")
