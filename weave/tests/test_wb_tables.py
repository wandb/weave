import wandb
import weave
from weave.language_features.tagging.tagged_value_type import TaggedValueType
from weave.ops_domain.wandb_domain_gql import _make_alias
from weave.ops_domain import wbmedia
import numpy as np
from weave.ops_arrow.list_ops import filter


def use_static_artifact_node(
    fake_wandb,
    entity_name="test_entity",
    project_name="test_project",
    collection_name="joined_table_artifact",
    version="latest",
) -> weave.graph.Node:
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
    return weave.ops.project(entity_name, project_name).artifactVersion(
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
                            "score": weave.types.optional(weave.types.Float()),
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
            "1": weave.types.optional(weave.types.Float()),
            "2": weave.types.optional(weave.types.Float()),
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
    grouped = table_rows.groupby(lambda row: weave.ops.dict_(label=row["label"]))
    sorted = grouped.sort(
        lambda row: weave.ops.make_list(a=row.groupkey()["label"]), ["asc"]
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
    grouped = filtered.groupby(lambda row: weave.ops.dict_(label=row["label"]))
    sorted = grouped.sort(
        lambda row: weave.ops.make_list(a=row.groupkey()["label"]), ["asc"]
    )
    res = weave.use(sorted)
    assert res.to_pylist_raw() == []
