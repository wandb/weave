import typing

import weave
from weave import registry_mem
from weave.legacy.ops_domain import run_ops, wb_domain_types

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


GHOSTWRITE_MD = weave.legacy.ops.Markdown(
    """
# [ghostwrite.ai](https://ghostwrite.ai).

Ghostwrite is a tool for writing. Our mission is to increase human creativity.
"""
)


@weave.op()
def fakewandbmodel_render(
    model_node: weave.Node[FakeWandbModel],
) -> weave.legacy.panels.Card:
    model = typing.cast(FakeWandbModel, model_node)
    return weave.legacy.panels.Card(
        title=model.name,
        subtitle="",
        content=[
            weave.legacy.panels.CardTab(
                name="Description",
                content=weave.legacy.panels.PanelMarkdown(GHOSTWRITE_MD),  # type: ignore
            ),
            weave.legacy.panels.CardTab(
                name="Predictions",
                content=weave.legacy.ops.project("shawn", "ghostwrite-test1")
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
) -> weave.legacy.panels.Card:
    entity = typing.cast(wb_domain_types.Entity, entity_node)
    return weave.legacy.panels.Card(
        title=entity_name_op(entity),
        subtitle="",
        content=[
            weave.legacy.panels.CardTab(
                name="Projects",
                content=weave.legacy.panels.Table(
                    entity.projects(),  # type: ignore
                    columns=[
                        lambda project: weave.legacy.panels.WeaveLink(
                            project_name_op(project),
                            vars={
                                "entity_name": entity_name_op(project.entity()),
                                "project_name": project_name_op(project),
                            },
                            to=lambda input, vars: weave.legacy.ops.project(
                                vars["entity_name"], vars["project_name"]
                            ),
                        ),
                    ],
                ),
            ),
            weave.legacy.panels.CardTab(
                name="Registered Models",
                content=weave.legacy.panels.Table(
                    weave.save(
                        ["ghostwrite", "credit card predictor", "stopsigns3"],
                        name="model_list",
                    ),
                    columns=[
                        lambda model_name: weave.legacy.panels.WeaveLink(
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


@weave.type()
class ProjectRunsTable(weave.Panel):
    id = "project-runs-table"
    input_node: weave.Node[list[wb_domain_types.Run]]

    @weave.op()
    def render(self) -> weave.legacy.panels.Table:
        return weave.legacy.panels.Table(
            self.input_node,
            columns=[
                lambda run: weave.legacy.panels.WeaveLink(
                    run.id(),
                    vars={
                        "entity_name": entity_name_op(run.project().entity()),
                        "project_name": project_name_op(run.project()),
                        "run_id": run.id(),
                    },
                    to=lambda input, vars: weave.legacy.ops.project(
                        vars["entity_name"], vars["project_name"]
                    ).run(vars["run_id"]),
                ),
                lambda run: run_ops.run_name(run),
                lambda run: run.createdAt(),
            ],
        )


@weave.type()
class ProjectArtifactsTable(weave.Panel):
    id = "project-artifacts-table"
    input_node: weave.Node[list[wb_domain_types.ArtifactCollection]]

    @weave.op()
    def render(self) -> weave.legacy.panels.Table:
        # This breaks if there is a variable in the node
        # types_names = weave.use(artifacts._get_op("type")().name().unique())
        # return weave.legacy.panels.Card(
        #     title="Artifacts",
        #     subtitle="",
        #     content=[
        #         weave.legacy.panels.CardTab(name=type_name, content=[type_name])
        #         for type_name in types_names
        #     ],
        # )
        return weave.legacy.panels.Table(
            self.input_node,
            columns=[
                lambda artifact: weave.legacy.panels.WeaveLink(
                    artifact._get_op("name")(),
                    vars={
                        "entity_name": entity_name_op(artifact.project().entity()),
                        "project_name": project_name_op(artifact.project()),
                        "artifact_name": artifact._get_op("name")(),
                    },
                    to=lambda input, vars: weave.legacy.ops.project(
                        vars["entity_name"], vars["project_name"]
                    ).artifact(vars["artifact_name"]),
                ),
                lambda artifact: artifact.createdAt(),
            ],
        )
