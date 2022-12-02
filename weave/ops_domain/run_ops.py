import typing

from . import wb_util
from ..api import op
from . import wb_domain_types
from .. import weave_types as types
from ..language_features.tagging import make_tag_getter_op

run_tag_getter_op = make_tag_getter_op.make_tag_getter_op(
    "run", wb_domain_types.Run.WeaveType(), op_name="tag-run"  # type: ignore
)


@op(name="run-jobType")
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

@op()
def _refine_history(run: wb_domain_types.Run) -> dict[str, typing.Any]:
    import pdb; pdb.set_trace()
    return run.sdk_obj._attrs['historyKeys']

@op(name="run-history", refine_output_type=_refine_history)
def history(run: wb_domain_types.Run) -> dict[str, typing.Any]:
    # This samples the history - once Shawn's GQL stuff lands and
    # we get the keys for the columns, we can probably convert this to
    # `scan_history` which is an iterator over all rows with a key
    # selection. For now this will suffice in terms of building Weave1.
    # Additonally, with Shawn's new "runs2" implementation, this might 
    # be completely rewritten.
    return [wb_util.process_run_dict_obj(row) for row in run.sdk_obj.scan_history(max_step=500)]


@op(name="run-createdAt")
def created_at(run: wb_domain_types.Run) -> wb_domain_types.Date:
    return wb_domain_types.Date(run.sdk_obj.created_at)


@op(name="run-usedArtifactVersions")
def used_artifact_versions(
    run: wb_domain_types.Run,
) -> list[wb_domain_types.ArtifactVersion]:
    # TODO: Create custom query
    return [
        wb_domain_types.ArtifactVersion.from_sdk_obj(v)
        for v in run.sdk_obj.used_artifacts()
    ]
