import weave

from ...ops_domain import wb_domain_types
from ...ops_domain import run_ops
from ... import registry_mem

run_project_op = registry_mem.memory_registry.get_op("run-project")
project_entity_op = registry_mem.memory_registry.get_op("project-entity")
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
