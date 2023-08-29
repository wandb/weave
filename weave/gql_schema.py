import typing
import graphql

from . import environment
from . import wandb_client_api

_GQL_SCHEMA_CACHE: dict[typing.Optional[str], graphql.GraphQLSchema] = {}


def gql_schema() -> graphql.GraphQLSchema:
    schema_path = environment.gql_schema_path()
    should_introspect = schema_path is None
    gql_schema = _GQL_SCHEMA_CACHE.get(schema_path)

    if gql_schema is None:
        if should_introspect:
            gql_schema = wandb_client_api.introspect_server_schema()

        else:
            with open(schema_path, "r") as f:
                schema_str = f.read()

            gql_schema = graphql.build_schema(schema_str)
    _GQL_SCHEMA_CACHE[schema_path] = gql_schema
    return gql_schema
