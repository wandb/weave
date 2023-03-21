import weave

from ...ops_domain import wb_domain_types
from ...ops_domain import run_ops
from ... import registry_mem

# We can't chain ops called .name() because of a weird bug :( [its a field on VarNode].
# So we have to get the ops here and call them directly for now.
project_name_op = registry_mem.memory_registry.get_op("project-name")
entity_name_op = registry_mem.memory_registry.get_op("entity-name")


@weave.op()
def runs_render(
    runs: weave.Node[list[wb_domain_types.Run]],
) -> weave.panels.Table:
    return weave.panels.Table(
        runs,
        columns=[
            lambda run: weave.panels.WeaveLink(
                run.id(),
                vars={
                    "entity_name": entity_name_op(run.project().entity()),
                    "project_name": project_name_op(run.project()),
                    "run_id": run.id(),
                },
                to=lambda input, vars: weave.ops.project(
                    vars["entity_name"], vars["project_name"]
                ).run(vars["run_id"]),
            ),
            lambda run: run_ops.run_name(run),
            lambda run: run.createdAt(),
        ],
    )
