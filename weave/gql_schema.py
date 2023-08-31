import typing
import graphql

from . import environment
from . import wandb_client_api

_GQL_SCHEMA_CACHE: dict[typing.Optional[str], graphql.GraphQLSchema] = {}


def gql_schema() -> graphql.GraphQLSchema:
    schema_path = environment.gql_schema_path()
    gql_schema = _GQL_SCHEMA_CACHE.get(schema_path)

    if gql_schema is None:
        if schema_path is not None:
            with open(schema_path, "r") as f:
                schema_str = f.read()

            gql_schema = graphql.build_schema(schema_str)
        else:
            gql_schema = wandb_client_api.introspect_server_schema()

        _GQL_SCHEMA_CACHE[schema_path] = gql_schema

    return gql_schema
