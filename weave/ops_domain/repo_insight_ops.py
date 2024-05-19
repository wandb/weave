import datetime
import json
from ..gql_op_plugin import wb_gql_op_plugin
from ..api import op
from .wandb_domain_gql import (
    _make_alias,
)

from ..gql_json_cache import use_json
from .. import weave_types as types
from .. import errors


rpt_op_configs = {
    "weekly_users_by_country_by_repo": types.TypedDict(
        {
            "user_fraction": types.Number(),
            "country": types.String(),
            "created_week": types.Timestamp(),
            "framework": types.String(),
        }
    ),
    "weekly_repo_users_by_persona": types.TypedDict(
        {
            "created_week": types.Timestamp(),
            "framework": types.String(),
            "persona": types.String(),
            "percentage": types.Number(),
        }
    ),
    "weekly_engaged_user_count_by_repo": types.TypedDict(
        {
            "created_week": types.Timestamp(),
            "framework": types.String(),
            "user_count": types.Number(),
        }
    ),
    "repo_gpu_backends": types.TypedDict(
        {
            "created_week": types.Timestamp(),
            "framework": types.String(),
            "gpu": types.String(),
            "percentage": types.Number(),
        }
    ),
    "versus_other_repos": types.TypedDict(
        {
            "created_week": types.Timestamp(),
            "framework": types.String(),
            "percentage": types.Number(),
        }
    ),
    "runtime_buckets": types.TypedDict(
        {
            "created_week": types.Timestamp(),
            "framework": types.String(),
            "bucket": types.String(),
            "bucket_run_percentage": types.Number(),
        }
    ),
    "user_model_train_freq": types.TypedDict(
        {
            "created_week": types.Timestamp(),
            "framework": types.String(),
            "train_freq": types.String(),
            "percentage": types.Number(),
        }
    ),
    "runs_versus_other_repos": types.TypedDict(
        {
            "created_week": types.Timestamp(),
            "framework": types.String(),
            "percentage": types.Number(),
        }
    ),
    "product_usage": types.TypedDict(
        {
            "created_week": types.Timestamp(),
            "framework": types.String(),
            "product": types.String(),
            "percentage": types.Number(),
        }
    ),
}


def make_rpt_op(plot_name, output_row_type):
    output_type = types.TypedDict(
        {
            "rows": types.List(output_row_type),
            "isNormalizedUserCount": types.Boolean(),
        }
    )

    @op(
        name=f"rpt_{plot_name}GQLResolver",
        input_type={"gql_result": types.TypedDict({}), "repoName": types.String()},
        output_type=output_type,
        hidden=True,
    )
    def root_all_projects_gql_resolver(gql_result, repoName):
        # Copied from root.ts
        alias = _make_alias(
            repoName,
            plot_name,
            "first: 100000",
            prefix="repoInsightsPlotData",
        )
        res = gql_result[alias]
        raw_rows = [use_json(edge["node"]["row"]) for edge in res["edges"]]
        schema_str = res.get("schema", "[]")
        schema = use_json(schema_str)

        is_normalized_user_count = res.get("isNormalizedUserCount", False)

        if not schema:
            raise errors.WeaveInternalError(f"No schema for {alias}")

        def process_row(row):
            processed_row = {}
            for i in range(len(schema)):
                name = schema[i]["Name"]
                type = schema[i]["Type"]
                if type == "TIMESTAMP":
                    processed_row[name] = datetime.datetime.fromtimestamp(row[i])
                else:
                    processed_row[name] = row[i]
            return processed_row

        rows = [process_row(row) for row in raw_rows]

        return {
            "rows": rows,
            "isNormalizedUserCount": is_normalized_user_count,
        }

    def plugin_fn(inputs, inner):
        alias = _make_alias(
            inputs.raw["repoName"],
            plot_name,
            "first: 100000",
            prefix="repoInsightsPlotData",
        )
        return f"""
            {alias}: repoInsightsPlotData(plotName: {json.dumps(plot_name)}, repoName: {inputs["repoName"]}, first: 100000) {{
                edges {{
                    node {{
                        row
                    }}
                }}
                schema
                isNormalizedUserCount
            }}"""

    @op(
        name=f"rpt_{plot_name}",
        input_type={"repoName": types.String()},
        output_type=output_type,
        plugins=wb_gql_op_plugin(
            plugin_fn,
            is_root=True,
            root_resolver=root_all_projects_gql_resolver,
        ),
        hidden=True,
    )
    def root_rpt(repoName):
        raise errors.WeaveGQLCompileError(
            "root-allProjects should not be executed directly. If you see this error, it is a bug in the Weave compiler."
        )

    return root_rpt


# Make all the ops!
for plot_name, output_row_type in rpt_op_configs.items():
    make_rpt_op(plot_name, output_row_type)


@op(
    name="normalizeUserCounts",
    input_type={
        "arr": types.List(
            types.TypedDict(
                {
                    "created_week": types.Timestamp(),
                    "user_count": types.Number(),
                }
            )
        ),
        "normalize": types.Boolean(),
    },
    output_type=lambda input_types: input_types["arr"],
)
def normalize_user_counts(arr, normalize):
    if len(arr) == 0 or not normalize:
        return arr
    min_date = min(arr, key=lambda x: x["created_week"])["created_week"]
    norm_factor = sum(x["user_count"] for x in arr if x["created_week"] == min_date)
    res = []
    for row in arr:
        r = row.copy()
        r["user_count"] = row["user_count"] / norm_factor
        res.append(r)
    return res
