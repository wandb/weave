import logging
from .. import weave_types as types
from ..api import op
from . import wb_domain_types as wdt
from ..wandb_api import wandb_gql_query
from ..language_features.tagging import tagged_value_type
from .. import engine_trace

# This op replaces all domain root ops in the graph during the compilation step.
# It executes a GQL query (that is constructed inside of `compile_domain.py`)
# and returns the results as a weave type.
@op(
    name="gqlroot-wbgqlquery",
    input_type={
        "query_str": types.String(),
        "output_type": types.TypeType(),
    },
    output_type=types.Any(),
)
def wbgqlquery(query_str, output_type):
    tracer = engine_trace.tracer()
    with tracer.trace("wbgqlquery:public_api"):
        logging.info("Executing GQL query: %s", query_str)
        gql_payload = wandb_gql_query(query_str)
    values = list(gql_payload.values())
    if len(values) != 1:
        raise ValueError("GQL query should return exactly one value")
    if isinstance(output_type, tagged_value_type.TaggedValueType):
        output_type = output_type.value
    if output_type.instance_class is None or not issubclass(
        output_type.instance_class, wdt.GQLTypeMixin
    ):
        raise ValueError(
            f"Invalid output type for gqlroot-wbgqlquery, must be a GQLTypeMixin, got {output_type}"
        )
    res = output_type.instance_class.from_gql(values[0])
    return res


# This variant is used by root ops which need custom logic to parse the results
@op(
    name="gqlroot-wbgqlquery_custom",
    input_type={
        "query_str": types.String(),
    },
    output_type=types.TypedDict({}),
)
def wbgqlquery_custom(query_str):
    tracer = engine_trace.tracer()
    with tracer.trace("wbgqlquery_custom:public_api"):
        logging.info("Executing GQL query: %s", query_str)
        gql_payload = wandb_gql_query(query_str)
    return gql_payload
