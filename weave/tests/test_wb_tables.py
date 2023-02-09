import wandb
import weave
from weave.artifact_local import LocalArtifact, LocalArtifactType
from weave.ops_domain.wandb_domain_gql import _make_alias
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
