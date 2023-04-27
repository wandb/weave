import typing
import weave

from ...ops_domain import wb_domain_types
from ...ops_domain import run_ops
from ... import registry_mem

# We can't chain ops called .name() because of a weird bug :( [its a field on VarNode].
# So we have to get the ops here and call them directly for now.
project_name_op = registry_mem.memory_registry.get_op("project-name")
entity_name_op = registry_mem.memory_registry.get_op("entity-name")
user_name_op = registry_mem.memory_registry.get_op("user-name")


@weave.type()
class FakeWandbModel:
    name: str


@weave.op(
    render_info={"type": "function"},
)
def org_model(entity_name: str, model_name: str) -> FakeWandbModel:
    return FakeWandbModel(model_name)


GHOSTWRITE_MD = weave.ops.Markdown(
    """
# [ghostwrite.ai](https://ghostwrite.ai).

Ghostwrite is a tool for writing. Our mission is to increase human creativity.
"""
)


@weave.op()
def fakewandbmodel_render(
    model_node: weave.Node[FakeWandbModel],
) -> weave.panels.Card:
    model = typing.cast(FakeWandbModel, model_node)
    return weave.panels.Card(
        title=model.name,
        subtitle="",
        content=[
            weave.panels.CardTab(
                name="Description",
                content=weave.panels.PanelMarkdown(GHOSTWRITE_MD),  # type: ignore
            ),
            weave.panels.CardTab(
                name="Predictions",
                content=weave.ops.project("shawn", "ghostwrite-test1")
                .runs()
                .summary()["predictions"]
                .table()
                .rows()
                .concat()
                .to_py(),
            ),
        ],
    )


@weave.op()
def entity_render(
    entity_node: weave.Node[wb_domain_types.Entity],
) -> weave.panels.Card:
    entity = typing.cast(wb_domain_types.Entity, entity_node)
    return weave.panels.Card(
        title=entity_name_op(entity),
        subtitle="",
        content=[
            weave.panels.CardTab(
                name="Projects",
                content=weave.panels.Table(
                    entity.projects(),  # type: ignore
                    columns=[
                        lambda project: weave.panels.WeaveLink(
                            project_name_op(project),
                            vars={
                                "entity_name": entity_name_op(project.entity()),
                                "project_name": project_name_op(project),
                            },
                            to=lambda input, vars: weave.ops.project(
                                vars["entity_name"], vars["project_name"]
                            ),
                        ),
                    ],
                ),
            ),
            weave.panels.CardTab(
                name="Registered Models",
                content=weave.panels.Table(
                    weave.save(
                        ["ghostwrite", "credit card predictor", "stopsigns3"],
                        name="model_list",
                    ),
                    columns=[
                        lambda model_name: weave.panels.WeaveLink(
                            model_name,
                            vars={
                                "entity_name": entity_name_op(entity),
                            },
                            to=lambda input, vars: org_model(
                                vars["entity_name"], input
                            ),
                        ),
                    ],
                ),
            ),
        ],
    )


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
