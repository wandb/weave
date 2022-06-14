import typing
import weave
from sklearn.datasets import fetch_california_housing
from weave import panels

from .. import panel_util

# @weave.op()
# def confusion_matrix(
#     inp: typing.Any, guess_col: str, truth_col: str, compare_col: str
# ) -> weave.panels.Facet:
#     return weave.panels.Facet(
#         input_node=inp,
#         x=lambda i: i[guess_col],
#         y=lambda i: i[truth_col],
#         select=lambda cell: cell.count(),
#     )
@weave.type()
class User:
    name: str


def get_ca_housing_dataset(size: int):
    housing = fetch_california_housing(as_frame=True)
    housingdf = housing.frame.iloc[:size]
    return weave.ops.dataframe_to_arrow(housingdf)


@weave.op(
    render_info={"type": "function"},
    output_type=weave.type_of(get_ca_housing_dataset(100)),
)
def ca_housing_dataset(size: int):
    return get_ca_housing_dataset(size)


@weave.op()
def table_summary(table: typing.Any) -> typing.Sequence[weave.panels.Panel]:
    if not table:
        return []
    col_names = list(weave.use(table[0]).keys())
    cols = {col_name: table.pick(col_name) for col_name in col_names}
    panels = []
    for col_name, col_values in cols.items():
        panels.append(weave.panels.LabeledItem(item=col_values, label=col_name))
    return panels


@weave.type()
class Dataset:
    name: str
    description: str
    created_by: User
    updated_at: str  # TODO: timestamp
    table: weave.ops.ArrowWeaveList


@weave.op()
def ca_housing_dataset_card(dataset: Dataset) -> panels.Card:
    # Issue, we are copying the data into the panel as consts instead of
    # passing in the methods needed to fetch it.
    # This would not be editable in the UI.
    # PanelPlot doesn't work because
    return panels.Card(
        title=dataset.name,
        subtitle=dataset.created_by.name,
        content=[
            panels.CardTab(
                name="Overview",
                content=panels.Group(
                    items=[
                        panels.Group(
                            prefer_horizontal=True,
                            items=[
                                panels.LabeledItem(
                                    item=dataset.updated_at, label="Last updated"
                                ),
                                # panels.LabeledItem(
                                #     item=model_card.model_type, label="Model type"
                                # ),
                                # panels.LabeledItem(
                                #     item=model_card.primary_metric.name, label="Metric"
                                # ),
                            ],
                        ),
                        panels.LabeledItem(
                            item=dataset.description, label="Description"
                        ),
                        # panels.LabeledItem(
                        #     item=dataset.table, height=500, label="Data"
                        # ),
                    ]
                ),
            ),
            panels.CardTab(
                name="Limitations & Use",
                content=panels.LabeledItem(item="tab2", label="tab2-label"),
            ),
            panels.CardTab(
                name="Data",
                content=panels.LabeledItem(item=dataset.table, height=500, label=""),
            ),
            panels.CardTab(
                name="Plot",
                content=panels.Plot(
                    input_node=panel_util.child_item(dataset.table),
                    x=lambda row: row["Longitude"],
                    y=lambda row: row["Latitude"],
                ),
            ),
        ]
        # panels.CardTab(
        #     name="Summary",
        #     content=panels.LabeledItem(
        #         item=table_summary(dataset.table), height=500, label=""
        #     ),
        # ),
    )
