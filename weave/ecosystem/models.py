import weave
from weave import panels

# This Type should be built-in to Weave, declared in weave.types
@weave.type()
class User:
    name: str


# This Type will be a built-in to Weave, declared in weave.types
@weave.type()
class TargetMetric:
    name: str
    direction: str  # typing.Union['up','down']  # (TODO: enum)


@weave.type()
class ModelCard:
    model_name: str
    created_by: User
    updated_at: str  # TODO: timestamp
    model_type: str  # TODO: enum
    primary_metric: TargetMetric
    application: str

    # TODO: This is not general enough. It should depend on the type of the model
    example: str  # Maybe should be type MarkdownString so we know to use a Markdown renderer


# This should be an op, so we can call it from the UI, but I need to fix something
# to make that work
@weave.op()
def model_card_panel(model_card: ModelCard) -> panels.Card:
    return panels.Card(
        title=model_card.model_name,
        subtitle=model_card.created_by.name,
        content=[
            panels.CardTab(
                name="Overview",
                content=panels.Group(
                    items=[
                        panels.Group(
                            prefer_horizontal=True,
                            items=[
                                panels.LabeledItem(
                                    item=model_card.updated_at, label="Last updated"
                                ),
                                panels.LabeledItem(
                                    item=model_card.model_type, label="Model type"
                                ),
                                panels.LabeledItem(
                                    item=model_card.primary_metric.name, label="Metric"
                                ),
                            ],
                        ),
                        panels.LabeledItem(
                            item=model_card.application, label="Application"
                        ),
                        panels.LabeledItem(item=model_card.example, label="Example"),
                    ]
                ),
            ),
            panels.CardTab(
                name="Limitations & Use",
                content=panels.LabeledItem(item="tab2", label="tab2-label"),
            ),
        ],
    )
