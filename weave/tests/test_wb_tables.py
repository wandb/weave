import wandb
import weave
from weave.artifact_local import LocalArtifact, LocalArtifactType
from weave.ops_domain.wandb_domain_gql import _make_alias
from weave.ops_domain import wbmedia
from weave.ops_domain import table
from ..weave_internal import make_const_node

from ..artifact_wandb import WandbArtifact, WandbArtifactType, WeaveWBArtifactURI
from .fixture_fakewandb import FakeApi

from wandb.apis.public import Artifact as PublicArtifact
import os


def use_static_artifact_node(
    fake_wandb,
    entity_name="test_entity",
    project_name="test_project",
    collection_name="joined_table_artifact",
    version="latest",
) -> weave.graph.Node:
    fake_wandb.fake_api.add_mock(
        lambda ndx, q: {
            "project_5702147f0293fd7538d402af13069708": {
                "id": "p1",
                "name": project_name,
                "entity": {"id": "e1", "name": entity_name},
                _make_alias(
                    f'name: "{collection_name}:{version}"', prefix="artifact"
                ): {
                    "id": "a1",
                    "versionIndex": "0",
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
                    "artifact": "wandb-artifact:///test_entity/test_project/test_name:v0",
                    "path": "media/html/03ac15e611be692f058e.html",
                }
            ]
        }
    ]
