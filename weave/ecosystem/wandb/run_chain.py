import weave
import json
import typing

from ... import ops_arrow
from ... import op_def
from ... import compile

from . import gql_artifact_dag


@weave.type()
class RunChainSegmentInfo:
    run_name: str
    final_step: typing.Optional[int]


@weave.type()
class RunChain:
    entity_name: str
    project_name: str
    segments: list[RunChainSegmentInfo]

    def _history_node(self):
        with op_def.no_refine():
            proj = weave.ops.project(self.entity_name, self.project_name)
            history_nodes = []
            for seg in self.segments:
                # This is the only use of the deprecated history2 op in the Weave
                # codebase. We should be able to update to history3, but we'll
                # wait til we come back to working on this.
                hist_node = proj.run(seg.run_name).history2()
                if seg.final_step != None:
                    hist_node = hist_node.limit(seg.final_step)

                history_nodes.append(hist_node)

            history_node = weave.ops.List.concat(
                weave.ops.make_list(
                    **{f"node{i}": n for i, n in enumerate(history_nodes)}
                )
            )
            return history_node

    @weave.op()
    def refine_history_type(self) -> weave.types.Type:
        return compile.compile([self._history_node()])[0].type

    @weave.op(
        output_type=ops_arrow.ArrowWeaveListType(weave.types.TypedDict({})),
        refine_output_type=refine_history_type,
    )
    def history(self):
        return self._history_node()


# This is cacheable, since runs set their checkpoint artifact on startup.
@weave.op(render_info={"type": "function"})
def run_chain(run_path: str) -> RunChain:
    with op_def.no_refine():
        entity, project, run_id = run_path.split("/")
        proj = weave.ops.project(entity, project)
        run = proj.run(run_id)

        # Get the checkpoint artifact for this one if one exists
        used_arts = run.usedArtifactVersions()
        used_art_names = used_arts.name()
        used_art_type_names = used_arts.artifactType().name()
        with compile.enable_compile():
            res = weave.use((used_art_names, used_art_type_names))

        checkpoint_names = []
        for name, type_name in zip(res[0], res[1]):
            if type_name == "checkpoint":
                checkpoint_names.append(name)
        if len(checkpoint_names) == 0:
            return RunChain(
                entity_name=entity,
                project_name=project,
                segments=[RunChainSegmentInfo(run_name=run_id, final_step=None)],
            )
        if len(checkpoint_names) > 1:
            raise Exception("Multiple checkpoints found")
        checkpoint_name = checkpoint_names[0]

        # Get the sequence of runs and checkpoints that lead here.
        seq = gql_artifact_dag.get_run_checkpoint_chain(
            entity, project, checkpoint_name
        )

        # Fetch the contents of the checkpoint file for all checkpoints so we can get
        # the step for each.
        checkpoint_artifact_info = [s[1] for s in seq]
        nodes = []
        for artifact_info in checkpoint_artifact_info:
            checkpoint_json_node = (
                proj.artifactVersion(
                    artifact_info["artifactSequenceName"],
                    artifact_info["artifactCommitHash"],
                )
                .file("checkpoint.json")
                .contents()
            )
            nodes.append(checkpoint_json_node)

        with compile.enable_compile():
            checkpoint_jsons = weave.use(nodes)
        checkpoint_steps = [json.loads(c)["step"] for c in checkpoint_jsons]
        run_infos = [s[0] for s in seq]

        # Construct our segment objects.
        segments = []
        for run_info, checkpoint_step in zip(run_infos, checkpoint_steps):
            segments.append(
                RunChainSegmentInfo(
                    run_name=run_info["runName"], final_step=checkpoint_step
                )
            )
        segments.append(
            RunChainSegmentInfo(run_name=run_infos[-1]["runName"], final_step=None)
        )
        return RunChain(entity_name=entity, project_name=project, segments=segments)
