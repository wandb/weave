import typing

from . import wb_util
from ..api import op
from . import wb_domain_types
from .. import weave_types as types
from ..language_features.tagging import make_tag_getter_op

run_tag_getter_op = make_tag_getter_op.make_tag_getter_op(
    "run", wb_domain_types.Run.WeaveType(), op_name="tag-run"  # type: ignore
)


@op(name="run-jobtype")
def jobtype(run: wb_domain_types.Run) -> str:
    return run.sdk_obj.jobType


@op(name="run-name")
def name(run: wb_domain_types.Run) -> str:
    return run.sdk_obj.name


@op(name="run-link")
def link(run: wb_domain_types.Run) -> wb_domain_types.Link:
    return wb_domain_types.Link(
        run.sdk_obj.display_name,
        f"/{run._project._entity.entity_name}/{run._project.project_name}/runs/{run.run_id}",
    )


@op(name="run-id")
def id(run: wb_domain_types.Run) -> str:
    return run.sdk_obj.id


@op(render_info={"type": "function"})
def refine_summary_type(run: wb_domain_types.Run) -> types.Type:
    return wb_util.process_run_dict_type(run.sdk_obj.summary._json_dict)


@op(name="run-summary", refine_output_type=refine_summary_type)
def summary(run: wb_domain_types.Run) -> dict[str, typing.Any]:
    return wb_util.process_run_dict_obj(run.sdk_obj.summary._json_dict)


@op(render_info={"type": "function"})
def refine_config_type(run: wb_domain_types.Run) -> types.Type:
    return wb_util.process_run_dict_type(run.sdk_obj.config)


@op(name="run-config", refine_output_type=refine_config_type)
def config(run: wb_domain_types.Run) -> dict[str, typing.Any]:
    return wb_util.process_run_dict_obj(run.sdk_obj.config)


@op(name="run-usedArtifactVersions")
def used_artifact_versions(
    run: wb_domain_types.Run,
) -> list[wb_domain_types.ArtifactVersion]:
    # TODO: Create custom query
    return [
        wb_domain_types.ArtifactVersion.from_sdk_obj(v)
        for v in run.sdk_obj.used_artifacts()
    ]
