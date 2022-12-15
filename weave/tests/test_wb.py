import pytest

from .. import api as weave
from .. import ops as ops

from . import weavejs_ops
import json
from . import fixture_fakewandb as fwb
from .. import graph
from ..ops_domain import wb_domain_types as wdt
from ..ops_primitives import list_
from .. import weave_types as types

from .. import ops_arrow as arrow

file_path_response = {
    "project": {
        **fwb.project_payload,  # type: ignore
        "artifactType_46d22fef09db004187bb8da4b5e98c58": {
            **fwb.defaultArtifactType_payload,  # type: ignore
            "artifactCollections_21303e3890a1b6580998e6aa8a345859": {
                "edges": [
                    {
                        "node": {
                            **fwb.artifactSequence_payload,  # type: ignore
                            "artifacts_21303e3890a1b6580998e6aa8a345859": {
                                "edges": [{"node": fwb.artifactVersion_payload}]
                            },
                        }
                    }
                ]
            },
        },
    }
}

artifact_browser_response = {
    "project": {
        **fwb.project_payload,  # type: ignore
        "artifactCollection_d651817074b6a8074e87e9dfd5767726": {
            **fwb.artifactSequence_payload,  # type: ignore
            "artifactMembership_78e7a3fd51159b4fdfb0815be0b0f92c": fwb.artifactMembership_payload,
        },
    }
}


workspace_response = {
    "project": {
        **fwb.project_payload,  # type: ignore
        "runs_21303e3890a1b6580998e6aa8a345859": {
            "edges": [
                {
                    "node": {
                        **fwb.run_payload,  # type: ignore
                        "summaryMetrics": json.dumps(
                            {
                                "table": {
                                    "_type": "table-file",
                                    "artifact_path": "wandb-client-artifact://1234567890/test_results.table.json",
                                },
                                "legacy_table": {
                                    "_type": "table-file",
                                    "path": "media/tables/legacy_table.table.json",
                                },
                            }
                        ),
                        "displayName": "amber-glade-100",
                    }
                },
            ]
        },
    }
}

workspace_response_filtered = {
    "project": {
        **fwb.project_payload,  # type: ignore
        "runs_6e908597bd3152c2f0457f6283da76b9": {
            "edges": [
                {
                    "node": {
                        **fwb.run_payload,  # type: ignore
                        "summaryMetrics": json.dumps(
                            {
                                "table": {
                                    "_type": "table-file",
                                    "artifact_path": "wandb-client-artifact://1234567890/test_results.table.json",
                                }
                            }
                        ),
                        "displayName": "amber-glade-100",
                    }
                },
            ]
        },
    }
}

artifact_version_sdk_response = {
    "artifact": {
        **fwb.artifactVersion_payload,  # type: ignore
        "artifactType": fwb.defaultArtifactType_payload,
        "artifactSequence": {**fwb.artifactSequence_payload, "project": fwb.project_payload},  # type: ignore
    }
}


@pytest.mark.parametrize(
    "table_file_node, mock_response",
    [
        # Path used in weave demos
        (
            ops.project("stacey", "mendeleev")
            .artifactType("test_results")
            .artifacts()[0]
            .versions()[0]
            .file("test_results.table.json"),
            file_path_response,
        ),
        # Path used in artifact browser
        (
            ops.project("stacey", "mendeleev")
            .artifact("test_res_1fwmcd3q")
            .membershipForAlias("v0")
            .artifactVersion()
            .file("test_results.table.json"),
            artifact_browser_response,
        ),
    ],
)
def test_table_call(table_file_node, mock_response, fake_wandb):
    fake_wandb.add_mock(lambda q, ndx: mock_response)
    table_image0_node = table_file_node.table().rows()[0]["image"]
    table_image0 = weave.use(table_image0_node)
    assert table_image0.height == 299
    assert table_image0.width == 299
    assert table_image0.path.path == "media/images/6274b7484d7ed4b6ad1b.png"

    # artifactVersion is not currently callable on image node as a method.
    # TODO: fix
    image0_url_node = (
        ops.wbmedia.artifactVersion(table_image0_node)
        .file(
            "wandb-artifact://stacey/mendeleev/test_res_1fwmcd3q:v0?file=media%2Fimages%2F8f65e54dc684f7675aec.png"
        )
        .direct_url_as_of(1654358491562)
    )
    image0_url = weave.use(image0_url_node)
    assert image0_url.endswith(
        "testdata/wb_artifacts/test_res_1fwmcd3q_v0/media/images/8f65e54dc684f7675aec.png"
    )


def test_avfile_type(fake_wandb):
    fake_wandb.add_mock(lambda q, ndx: file_path_response)
    f = (
        ops.project("stacey", "mendeleev")
        .artifactType("test_results")
        .artifacts()[0]
        .versions()[0]
        .file("test_results.table.json")
    )
    t = weavejs_ops.file_type(f)
    # TODO: totally weird that this is a dict and not a string.
    assert weave.use(t) == {
        "type": "file",
        "extension": "json",
        "wbObjectType": {"type": "table"},
    }


def test_table_col_order_and_unknown_types(fake_wandb):
    fake_wandb.add_mock(lambda q, ndx: file_path_response)
    node = (
        ops.project("stacey", "mendeleev")
        .artifactType("test_results")
        .artifacts()[0]
        .versions()[0]
        .file("weird_table.table.json")
        .table()
    )
    assert weave.use(node.rows()[0]["c"]) == 9.93


def test_missing_file(fake_wandb):
    fake_wandb.add_mock(lambda q, ndx: file_path_response)
    node = (
        ops.project("stacey", "mendeleev")
        .artifactType("test_results")
        .artifacts()[0]
        .versions()[0]
        .file("does_not_exist")
    )
    assert weave.use(node) == None


def table_mock(q, ndx):
    if ndx == 0:
        return workspace_response
    elif ndx == 1:
        return artifact_version_sdk_response
    elif ndx == 2:
        return workspace_response


def test_legacy_run_file_table_format(fake_wandb):
    fake_wandb.add_mock(lambda q, ndx: workspace_response)
    cell_node = (
        ops.project("stacey", "mendeleev")
        .runs()
        .limit(1)
        .summary()["legacy_table"]
        .table()
        .rows()
        .dropna()
        .concat()
        .createIndexCheckpointTag()[1]["col1"]
    )
    assert weave.use(cell_node) == "c"
    assert weave.use(cell_node.indexCheckpoint()) == 1
    assert weave.use(cell_node.run().name()) == "amber-glade-100"
    assert weave.use(cell_node.project().name()) == "mendeleev"


def test_mapped_table_tags(fake_wandb):
    fake_wandb.add_mock(table_mock)
    cell_node = (
        ops.project("stacey", "mendeleev")
        .runs()
        .limit(1)
        .summary()["table"]
        .table()
        .rows()
        .dropna()
        .concat()
        .createIndexCheckpointTag()[5]["score_Amphibia"]
    )
    assert weave.use(cell_node.indexCheckpoint()) == 5
    assert weave.use(cell_node.run().name()) == "amber-glade-100"
    assert weave.use(cell_node.project().name()) == "mendeleev"


def test_table_tags_row_first(fake_wandb):
    fake_wandb.add_mock(table_mock)
    cell_node = (
        ops.project("stacey", "mendeleev")
        .runs()
        .limit(1)[0]
        .summary()["table"]
        .table()
        .rows()
        .createIndexCheckpointTag()[5]["score_Amphibia"]
    )
    assert weave.use(cell_node.indexCheckpoint()) == 5
    assert weave.use(cell_node.run().name()) == "amber-glade-100"
    assert weave.use(cell_node.project().name()) == "mendeleev"


def test_table_tags_column_first(fake_wandb):
    fake_wandb.add_mock(table_mock)
    cell_node = (
        ops.project("stacey", "mendeleev")
        .runs()
        .limit(1)[0]
        .summary()["table"]
        .table()
        .rows()
        .createIndexCheckpointTag()["score_Amphibia"][5]
    )
    assert weave.use(cell_node.indexCheckpoint()) == 5
    assert weave.use(cell_node.run().name()) == "amber-glade-100"
    assert weave.use(cell_node.project().name()) == "mendeleev"


def test_table_images(fake_wandb):
    fake_wandb.add_mock(table_mock)
    # Query 1:
    project_node = ops.project("stacey", "mendeleev")
    project_runs_node = project_node.runs().limit(1)
    summary_node = project_runs_node.summary()
    # this use is important as it models the sequence of calls in UI
    # and invokes the issues with artifact paths
    assert list(weave.use(summary_node)[0].keys()) == ["table", "legacy_table"]

    # Query 2:
    table_rows_node = summary_node.pick("table").table().rows()
    assert len(weave.use(table_rows_node)) == 1


def table_mock_filtered(q, ndx):
    if ndx == 0:
        return workspace_response_filtered
    elif ndx == 1:
        return artifact_version_sdk_response
    elif ndx == 2:
        return workspace_response_filtered


def test_tag_run_color_lookup(fake_wandb):
    fake_wandb.add_mock(table_mock_filtered)
    colors_node = weave.save(
        {"1ht5692d": "rgb(218, 76, 76)", "2ed5xwpn": "rgb(83, 135, 221)"}
    )
    run_id = (
        ops.project("stacey", "mendeleev")
        .filteredRuns("{}", "-createdAt")
        .limit(50)
        .summary()["table"]
        .table()
        .rows()
        .dropna()
        .concat()
        .createIndexCheckpointTag()[5]
        .run()
        .id()
    )
    run_color = colors_node[run_id]
    assert weave.use(run_color) == "rgb(83, 135, 221)"


def test_domain_gql_fragments(fake_wandb):
    fake_wandb.add_mock(
        lambda q, ndx: {
            "project": {
                **fwb.project_payload,
                "artifactType_46d22fef09db004187bb8da4b5e98c58": {
                    **fwb.defaultArtifactType_payload,
                    "artifactCollections_21303e3890a1b6580998e6aa8a345859": {
                        "edges": [
                            {
                                "node": {
                                    **fwb.artifactSequence_payload,
                                    "artifacts_21303e3890a1b6580998e6aa8a345859": {
                                        "edges": [
                                            {
                                                "node": {
                                                    **fwb.artifactVersion_payload,
                                                    "createdBy": {
                                                        "__typename": "Run",
                                                        **fwb.run_payload,
                                                        "displayName": "amber-glade-100",
                                                    },
                                                }
                                            }
                                        ]
                                    },
                                }
                            }
                        ]
                    },
                },
            }
        }
    )
    node = (
        ops.project("stacey", "mendeleev")
        .artifactType("test_results")
        .artifacts()[0]
        .versions()[0]
        .createdBy()
        .name()
    )
    assert weave.use(node) == "amber-glade-100"


def test_domain_gql_through_dicts_with_fn_nodes(fake_wandb):
    fake_wandb.add_mock(lambda q, ndx: workspace_response)
    project_node = ops.project("stacey", "mendeleev")
    project_name_node = project_node.name()
    entity_node = project_node.entity()
    entity_name_node = entity_node.name()
    runs_node = project_node.runs()

    # Make a function that returns a dict of the name of the row
    var_node = graph.VarNode(wdt.RunType, "row")
    inner_fn = graph.ConstNode(
        types.Function({"row": wdt.RunType}, types.TypedDict({"name": types.String()})),
        ops.dict_(name=ops.run_ops.run_name(var_node)),
    )

    run_names = runs_node.map(inner_fn)

    dict_node = ops.dict_(
        project_name=project_name_node,
        entity_name=entity_name_node,
        run_names=run_names,
    )
    assert weave.use(dict_node) == {
        "project_name": "mendeleev",
        "entity_name": "stacey",
        "run_names": [{"name": "amber-glade-100"}],
    }


def test_lambda_gql_stitch(fake_wandb):
    fake_wandb.add_mock(lambda q, ndx: {"project": fwb.project_payload})
    weave.use(
        ops.make_list(a="a", b="b", c="c").map(
            lambda x: x + ops.project("stacey", "mendeleev").name()
        )
    ) == None


def test_arrow_tag_serialization_can_handle_runs_in_concat(fake_wandb):
    fake_wandb.add_mock(table_mock_filtered)
    rows_node = (
        ops.project("stacey", "mendeleev")
        .filteredRuns("{}", "-createdAt")
        .limit(50)
        .summary()["table"]
        .table()
        .rows()
    )

    const_list = ops.make_list(l=rows_node, r=rows_node)
    concatted_list = list_.List.concat(const_list)
    concatted = arrow.concat(arr=concatted_list)

    # now get the run from the tags
    weave.use(ops.run_ops.run_tag_getter_op(concatted[0]))
