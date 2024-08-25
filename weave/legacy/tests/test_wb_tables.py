import time

import numpy as np
import wandb

import weave
from weave.legacy.weave.language_features.tagging import make_tag_getter_op
from weave.legacy.weave.language_features.tagging.tagged_value_type import TaggedValueType
from weave.legacy.weave.ops_arrow.list_ops import filter
from weave.legacy.weave.ops_domain import wbmedia
from weave.legacy.weave.ops_domain.wandb_domain_gql import _make_alias
from weave.legacy.weave.weave_internal import make_const_node


def use_static_artifact_node(
    fake_wandb,
    entity_name="test_entity",
    project_name="test_project",
    collection_name="joined_table_artifact",
    version="latest",
) -> weave.legacy.weave.graph.Node:
    fake_wandb.fake_api.add_mock(
        lambda q, ndx: {
            "project_5702147f0293fd7538d402af13069708": {
                "id": "p1",
                "name": project_name,
                "entity": {"id": "e1", "name": entity_name},
                _make_alias(
                    f'name: "{collection_name}:{version}"', prefix="artifact"
                ): {
                    "id": "a1",
                    "versionIndex": "0",
                    "commitHash": "1478438ajsdfjj3kj1nn1nj",
                    "artifactSequence": {
                        "id": "c1",
                        "name": collection_name,
                        "project": {
                            "id": "p1",
                            "name": project_name,
                            "entity": {"id": "e1", "name": entity_name},
                        },
                        "defaultArtifactType": {
                            "id": "at1",
                            "name": "art_type",
                            "project": {
                                "id": "p1",
                                "name": project_name,
                                "entity": {"id": "e1", "name": entity_name},
                            },
                        },
                    },
                },
            }
        }
    )
    return weave.legacy.weave.ops.project(entity_name, project_name).artifactVersion(
        collection_name, version
    )


def test_wb_joined_table(fake_wandb):
    art_node = use_static_artifact_node(
        fake_wandb, collection_name="joined_table_artifact"
    )
    rows_node = art_node.file("table.joined-table.json").joinedTable().rows()
    cell_node = rows_node[0]
    assert weave.use(rows_node.count()) == 15
    assert weave.use(cell_node) == {
        "0": {"t_1_to_t_2_card": "1-1", "val": "a2"},
        "1": {"t_1_to_t_2_card": "1-1", "val": "a1"},
    }


def test_wb_partitioned_table(fake_wandb):
    art_node = use_static_artifact_node(
        fake_wandb, collection_name="partitioned_table_artifact"
    )
    rows_node = art_node.file("table.partitioned-table.json").partitionedTable().rows()
    cell_node = rows_node[0]
    assert weave.use(rows_node.count()) == 3
    assert weave.use(cell_node) == {"a": 1.0, "b": 2.0, "c": 3.0}


def test_convert_optional_list_cell(fake_wandb):
    tab = wandb.Table(columns=["a"])
    tab.add_data([wandb.Html("<p>hello</p>")])
    art = wandb.Artifact("test_name", "test_type")
    art.add(tab, "table")
    art_node = fake_wandb.mock_artifact_as_node(art)
    file_node = art_node.file("table.table.json")
    table_node = file_node.table()
    table_rows = table_node.rows()
    awl = weave.use(table_rows)
    # The wandb library makes everything optional, which is what we want to
    # test here.
    # Make sure the mapped Weave1 type is what we expect.
    assert awl.object_type == weave.types.TypedDict(
        {
            "a": weave.types.optional(
                weave.types.List(wbmedia.HtmlArtifactFileRef.WeaveType())
            )
        }
    )
    assert awl.to_pylist_raw() == [
        {
            "a": [
                {
                    "artifact": f"wandb-artifact:///test_entity/test_project/test_name:{art.commit_hash}",
                    "path": "media/html/03ac15e611be692f058e.html",
                    "sha256": "d4935b7d4e8f30952d5869122ca6793114936be8bf156dd936b6794fb6715e02",
                }
            ]
        }
    ]


def _quick_image(val: int):
    return wandb.Image(np.ones((32, 32)) * val)


def test_join_table_with_images(fake_wandb):
    table1 = wandb.Table(
        columns=["name", "image"], data=[["a", _quick_image(1)], ["b", _quick_image(2)]]
    )
    table2 = wandb.Table(columns=["name", "score"], data=[["a", 1], ["b", 2]])
    jt = wandb.JoinedTable(table1, table2, "name")

    art = wandb.Artifact("test_name", "test_type")
    art.add(jt, "table")
    art_node = fake_wandb.mock_artifact_as_node(art)
    file_node = art_node.file("table.joined-table.json")
    table_node = file_node.table()
    table_rows = table_node.rows()
    awl = weave.use(table_rows)
    assert awl.object_type == TaggedValueType(
        weave.types.TypedDict(
            {
                "joinObj": weave.types.optional(weave.types.String()),
            }
        ),
        weave.types.TypedDict(
            {
                "0": weave.types.optional(
                    weave.types.TypedDict(
                        {
                            "name": weave.types.optional(weave.types.String()),
                            "image": weave.types.optional(
                                wbmedia.ImageArtifactFileRef.WeaveType()
                            ),
                        }
                    )
                ),
                "1": weave.types.optional(
                    weave.types.TypedDict(
                        {
                            "name": weave.types.optional(weave.types.String()),
                            "score": weave.types.optional(weave.types.Number()),
                        }
                    )
                ),
            }
        ),
    )
    assert awl.to_pylist_raw() == [
        {
            "_tag": {"joinObj": "a"},
            "_value": {
                "0": {
                    "name": "a",
                    "image": {
                        "artifact": f"wandb-artifact:///test_entity/test_project/test_name:{art.commit_hash}",
                        "path": "media/images/9d4f26b99a1d4d044b6c.png",
                        "format": "png",
                        "height": 32,
                        "width": 32,
                        "sha256": "e7bdc527afd649f51950b4524b0c15aecaf7f484448a6cdfcdc2ecd9bba0f5a7",
                        "boxes": {},
                        "masks": {},
                    },
                },
                "1": {"name": "a", "score": 1.0},
            },
        },
        {
            "_tag": {"joinObj": "b"},
            "_value": {
                "0": {
                    "name": "b",
                    "image": {
                        "artifact": f"wandb-artifact:///test_entity/test_project/test_name:{art.commit_hash}",
                        "path": "media/images/7fd26b0af1228fa077bb.png",
                        "format": "png",
                        "height": 32,
                        "width": 32,
                        "sha256": "61cd2467cff9f0666c730c57d065cfe834765ba26514b46f91735c750676876a",
                        "boxes": {},
                        "masks": {},
                    },
                },
                "1": {"name": "b", "score": 2.0},
            },
        },
    ]


def test_join_table_with_numeric_columns(fake_wandb):
    table = wandb.Table(columns=[1, 2], data=[[1, 2]])
    art = wandb.Artifact("test_name", "test_type")
    art.add(table, "table")
    art_node = fake_wandb.mock_artifact_as_node(art)
    file_node = art_node.file("table.table.json")
    table_node = file_node.table()
    table_rows = table_node.rows()
    awl = weave.use(table_rows)
    # We want to convert these columns to strings - it is intentional that the
    # input is numbers but the output is strings. This is because Typescript,
    # JSON, and Python all handle numeric keys slightly diffently, so we settle
    # on always using the string representation.
    assert awl.object_type == weave.types.TypedDict(
        {
            "1": weave.types.optional(weave.types.Number()),
            "2": weave.types.optional(weave.types.Number()),
        }
    )
    assert awl.to_pylist_raw() == [{"1": 1, "2": 2}]


def test_metric_table_join(fake_wandb):
    table = wandb.Table(
        columns=["id", "label", "score_1", "score_2", "score_3"],
        data=[
            [1, "cat", 1.1, 2.1, 3.1],
            [2, "dog", 1.2, 2.2, 3.2],
            [3, "cat", 1.3, 2.3, 3.3],
            [4, "dog", 1.4, 2.4, 3.4],
            [5, "mouse", 1.5, 2.5, 3.5],
        ],
    )
    art = wandb.Artifact("test_name", "test_type")
    art.add(table, "table")
    art_node = fake_wandb.mock_artifact_as_node(art)
    file_node = art_node.file("table.table.json")
    table_node = file_node.table()
    table_rows = table_node.rows().createIndexCheckpointTag()
    grouped = table_rows.groupby(lambda row: weave.legacy.weave.ops.dict_(label=row["label"]))
    sorted = grouped.sort(
        lambda row: weave.legacy.weave.ops.make_list(a=row.groupkey()["label"]), ["asc"]
    )
    group_col_0 = sorted[0].groupkey()["label"]
    group_col_1 = sorted[1].groupkey()["label"]
    group_col_2 = sorted[2].groupkey()["label"]
    res = weave.use([group_col_0, group_col_1, group_col_2])
    assert res == ["cat", "dog", "mouse"]


def test_empty_table(fake_wandb):
    table = wandb.Table(
        columns=["id", "label", "score_1", "score_2", "score_3"],
        data=[],
    )
    art = wandb.Artifact("test_name", "test_type")
    art.add(table, "table")
    art_node = fake_wandb.mock_artifact_as_node(art)
    file_node = art_node.file("table.table.json")
    table_node = file_node.table()
    table_rows = table_node.rows().createIndexCheckpointTag()
    filtered = filter(table_rows, lambda row: row["label"] == "cat")
    grouped = filtered.groupby(lambda row: weave.legacy.weave.ops.dict_(label=row["label"]))
    sorted = grouped.sort(
        lambda row: weave.legacy.weave.ops.make_list(a=row.groupkey()["label"]), ["asc"]
    )
    res = weave.use(sorted)
    assert res.to_pylist_raw() == []


def test_join_group_combo(fake_wandb):
    table_1 = wandb.Table(
        columns=["id", "label", "score"],
        data=[
            [1, "A", 1],
            [2, "A", 2],
            [3, "B", 3],
            [4, "B", 4],
            [5, "C", 5],
            [6, "C", 6],
        ],
    )
    art_1 = wandb.Artifact("test_name_1", "test_type_1")
    art_1.add(table_1, "table_1")

    table_2 = wandb.Table(
        columns=["id", "label", "score"],
        data=[
            [1, "A", 10],
            [2, "B", 20],
            [3, "B", 30],
            [4, "C", 40],
            [5, "C", 50],
            [6, "A", 60],
        ],
    )
    art_2 = wandb.Artifact("test_name_2", "test_type_2")
    art_2.add(table_2, "table_2")

    art_1_node = fake_wandb.mock_artifact_as_node(art_1)
    art_2_node = fake_wandb.mock_artifact_as_node(art_2)
    table_1_rows = art_1_node.file("table_1.table.json").table().rows()
    table_2_rows = art_2_node.file("table_2.table.json").table().rows()
    list_of_tables = weave.legacy.weave.ops.make_list(a=table_1_rows, b=table_2_rows).dropna()
    joined_tables = list_of_tables.joinAll(
        lambda row: weave.legacy.weave.ops.make_list(a=row["id"]), False
    )
    indexed = joined_tables.createIndexCheckpointTag()
    grouped = indexed.groupby(lambda row: weave.legacy.weave.ops.dict_(label=row["label"][0]))
    sorted = grouped.sort(
        lambda row: weave.legacy.weave.ops.make_list(label=row.groupkey()["label"]),
        ["asc"],
    )
    assert weave.use(sorted.count()) == 3
    assert weave.use(sorted[2].groupkey()["label"]) == "C"
    assert weave.use(sorted[1]["score"]).to_pylist_notags() == [
        [3.0, 30.0],
        [4.0, 40.0],
    ]

    join_obj = sorted[0].joinObj()[0]
    assert weave.use(join_obj) == [1.0]

    from weave.legacy.weave import context_state

    _loading_builtins_token = context_state.set_loading_built_ins()
    tag_getter_op = make_tag_getter_op.make_tag_getter_op(
        "_ct_fake_run", weave.types.String()
    )
    context_state.clear_loading_built_ins(_loading_builtins_token)
    run_names = sorted[0]["score"].mapEach(lambda row: tag_getter_op(row))
    use_run_names = weave.use(run_names)
    assert use_run_names.to_pylist_notags() == [
        ["test_run", "test_run"],
        ["test_run", "test_run"],
    ]


def test_group_by_const(fake_wandb):
    columns = ["id", "label", "score"]
    data = [
        [1, "A", 1],
        [2, "A", 2],
        [3, "B", 3],
        [4, "B", 4],
        [5, "C", 5],
        [6, "C", 6],
    ]
    table_1 = wandb.Table(
        columns=columns,
        data=data,
    )
    art_1 = wandb.Artifact("test_name_1", "test_type_1")
    art_1.add(table_1, "table_1")
    art_1_node = fake_wandb.mock_artifact_as_node(art_1)
    table_1_rows = art_1_node.file("table_1.table.json").table().rows()
    grouped = table_1_rows.groupby(
        lambda row: weave.legacy.weave.ops.dict_(
            a=make_const_node(weave.types.Boolean(), True)
        )
    )
    assert weave.use(grouped).to_pylist_notags() == [
        [dict(zip(columns, row)) for row in data]
    ]


def test_symbols_in_name(fake_wandb):
    columns = ["id", "label", "score"]
    data = [
        [1, "A", 1],
        [2, "A", 2],
        [3, "B", 3],
        [4, "B", 4],
        [5, "C", 5],
        [6, "C", 6],
    ]
    table_1 = wandb.Table(
        columns=columns,
        data=data,
    )
    art_1 = wandb.Artifact("test_name_1", "test_type_1")
    name_with_all_symbols_and_spaces = "table_1!@#$%^&*( )_+`~[]{}|;':\",./<>?"
    art_1.add(table_1, name_with_all_symbols_and_spaces)
    art_1_node = fake_wandb.mock_artifact_as_node(art_1)
    table_1_rows = (
        art_1_node.file(f"{name_with_all_symbols_and_spaces}.table.json").table().rows()
    )
    assert weave.use(table_1_rows).to_pylist_notags() == [
        dict(zip(columns, row)) for row in data
    ]


def test_column_sort(fake_wandb):
    columns = ["name", "number", "float", "timestamp"]
    row1 = ["a", 0, 0.124122143123, time.time()]
    row2 = ["b", 1, 100.124123412341, time.time() + 10]
    row3 = ["c", 2, 10000.123412341234, time.time() + 20]
    data = [row1, row2, row3]

    table_1 = wandb.Table(
        columns=columns,
        data=data,
    )
    art_1 = wandb.Artifact("test_name_1", "test_type_1")
    art_1.add(table_1, "table_1")
    art_1_node = fake_wandb.mock_artifact_as_node(art_1)
    rows = art_1_node.file("table_1.table.json").table().rows()

    for col in columns:
        sorted = rows.sort(
            lambda row: weave.legacy.weave.ops.make_list(label=row[col]), ["desc"]
        )
        assert weave.use(sorted).to_pylist_notags() == [
            dict(zip(columns, row)) for row in [row3, row2, row1]
        ]

        sorted = sorted.sort(
            lambda row: weave.legacy.weave.ops.make_list(label=row[col]), ["asc"]
        )
        assert weave.use(sorted).to_pylist_notags() == [
            dict(zip(columns, row)) for row in data
        ]

    # Additional test sorting typed timestamps
    sorted = rows.sort(
        lambda row: weave.legacy.weave.ops.make_list(label=row["timestamp"].toTimestamp()),
        ["desc"],
    )
    assert weave.use(sorted).to_pylist_notags() == [
        dict(zip(columns, row)) for row in [row3, row2, row1]
    ]

    sorted = sorted.sort(
        lambda row: weave.legacy.weave.ops.make_list(label=row["timestamp"].toTimestamp()),
        ["asc"],
    )
    assert weave.use(sorted).to_pylist_notags() == [
        dict(zip(columns, row)) for row in data
    ]


def test_group_avg_sort_combo(fake_wandb):
    columns = ["id", "label", "score"]
    data = [
        [1, "A", 1],
        [2, "A", 2],
        [3, "B", 3],
        [4, "B", 4],
        [5, "C", 5],
        [6, "C", 6],
    ]

    table_1 = wandb.Table(
        columns=columns,
        data=data,
    )
    art_1 = wandb.Artifact("test_name_1", "test_type_1")
    art_1.add(table_1, "table_1")
    art_1_node = fake_wandb.mock_artifact_as_node(art_1)
    rows = art_1_node.file("table_1.table.json").table().rows()

    grouped = rows.groupby(lambda row: weave.legacy.weave.ops.dict_(label=row["label"]))
    sorted = grouped.sort(
        lambda row: weave.legacy.weave.ops.make_list(label=row["score"].avg()), ["asc"]
    )
    assert weave.use(sorted[2].groupkey()["label"]) == "C"
