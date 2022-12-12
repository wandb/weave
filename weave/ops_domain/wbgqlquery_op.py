from .. import weave_types as types
from ..api import op
from . import wb_domain_types as wdt
from ..wandb_api import wandb_gql_query

# This op replaces all domain root ops in the graph during the compilation step.
# It executes a GQL query (that is constructed inside of `compile_domain.py`)
# and returns the results as a weave type.
@op(
    name="gqlroot-wbgqlquery",
    input_type={
        "query_str": types.String(),
        "output_type": types.Type(),
    },
    output_type=types.Any(),
)
def wbgqlquery(query_str, output_type):
    gql_payload = wandb_gql_query(query_str)
    values = list(gql_payload.values())
    if len(values) != 1:
        raise ValueError("GQL query should return exactly one value")
    if output_type.instance_class is None or not issubclass(
        output_type.instance_class, wdt.GQLTypeMixin
    ):
        raise ValueError(
            f"Invalid output type for gqlroot-wbgqlquery, must be a GQLTypeMixin, got {output_type}"
        )
    res = output_type.instance_class.from_gql(values[0])
    return res
