import cProfile
import json
import re

import numpy as np
import pytest
import wandb

from weave.legacy.weave import api as weave
from weave.legacy.weave import artifact_fs, artifact_wandb, compile, graph, ops, stitch, uris
from weave.legacy.weave import ops_arrow as arrow
from weave.legacy.weave import weave_types as types
from weave.legacy.weave.language_features.tagging.tagged_value_type import TaggedValueType
from weave.legacy.weave.ops_arrow import ArrowWeaveListType
from weave.legacy.weave.ops_domain import artifact_membership_ops as amo
from weave.legacy.weave.ops_domain import table, wb_util, wbmedia
from weave.legacy.weave.ops_domain import wb_domain_types as wdt
from weave.legacy.weave.ops_primitives import dict_, list_
from weave.legacy.weave.ops_primitives.file import _as_w0_dict_
from .test_wb_domain_ops import assert_gql_str_equal

from ...tests import fixture_fakewandb as fwb
from weave.legacy.tests.util import weavejs_ops

file_path_response = {
    "project_518fa79465d8ffaeb91015dce87e092f": {
        **fwb.project_payload,  # type: ignore
        "artifactType_46d22fef09db004187bb8da4b5e98c58": {
            **fwb.defaultArtifactType_payload,  # type: ignore
            "artifactCollections_c1233b7003317090ab5e2a75db4ad965": {
                "edges": [
                    {
                        "node": {
                            **fwb.artifactSequence_payload,  # type: ignore
                            "artifacts_c1233b7003317090ab5e2a75db4ad965": {
                                "edges": [{"node": fwb.artifactVersion_payload}]
                            },
                        }
                    }
                ]
            },
        },
    }
}

file_path_no_entity_response = {
    "project_518fa79465d8ffaeb91015dce87e092f": {
        **fwb.project_payload,  # type: ignore
        "artifactType_46d22fef09db004187bb8da4b5e98c58": {
            **fwb.defaultArtifactType_payload,  # type: ignore
            "artifactCollections_c1233b7003317090ab5e2a75db4ad965": {
                "edges": [
                    {
                        "node": {
                            **fwb.artifactSequence_payload,  # type: ignore
                            "artifacts_c1233b7003317090ab5e2a75db4ad965": {
                                "edges": [
                                    {"node": fwb.artifactVersion_no_entity_payload}
                                ]
                            },
                        }
                    }
                ]
            },
        },
    }
}

artifact_browser_response = {
    "project_518fa79465d8ffaeb91015dce87e092f": {
        **fwb.project_payload,  # type: ignore
        "artifactCollection_d651817074b6a8074e87e9dfd5767726": {
            **fwb.artifactSequence_payload,  # type: ignore
            "artifactMembership_78e7a3fd51159b4fdfb0815be0b0f92c": fwb.artifactMembership_payload,
        },
    }
}

workspace_response_run1_summary_metrics = json.dumps(
    {
        "table": {
            "_type": "table-file",
            "artifact_path": "wandb-client-artifact://1234567890/test_results.table.json",
        },
        "legacy_table": {
            "_type": "table-file",
            "path": "media/tables/legacy_table.table.json",
        },
        "image": {
            "height": 64,
            "sha256": "440fab0d6f537b4557a106fa7853453332650631ef580fd328c620bd8aa5a025",
            "path": "media/images/random_image_9_440fab0d6f537b4557a1.png",
            "size": 4228,
            "_type": "image-file",
            "width": 64,
            "format": "png",
        },
    }
)


workspace_response_run3_summary_metrics = json.dumps(
    {
        "table": {
            "_type": "table-file",
            "artifact_path": "wandb-client-artifact://1122334455/test_results.table.json",
        },
    }
)


def workspace_response(include_display_name=True):
    return {
        "project_518fa79465d8ffaeb91015dce87e092f": {
            **fwb.project_payload,  # type: ignore
            "runs_c1233b7003317090ab5e2a75db4ad965": {
                "edges": [
                    {
                        "node": {
                            **fwb.run_payload,  # type: ignore
                            "summaryMetricsSubset": workspace_response_run1_summary_metrics,
                            "summaryMetrics": workspace_response_run1_summary_metrics,
                            **(
                                {"displayName": "amber-glade-100"}
                                if include_display_name
                                else {}
                            ),
                        },
                    },
                    {
                        "node": {
                            **fwb.run2_payload,  # type: ignore
                            "summaryMetricsSubset": json.dumps({}),
                            "summaryMetrics": json.dumps({}),
                            **(
                                {"displayName": "run2-display_name"}
                                if include_display_name
                                else {}
                            ),
                        },
                    },
                    {
                        "node": {
                            **fwb.run3_payload,  # type: ignore
                            "summaryMetricsSubset": workspace_response_run3_summary_metrics,
                            "summaryMetrics": workspace_response_run3_summary_metrics,
                            **(
                                {"displayName": "run3-display_name"}
                                if include_display_name
                                else {}
                            ),
                        },
                    },
                ]
            },
        }
    }


workspace_response_no_run_displayname_run1_summary_metrics = json.dumps(
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
)

workspace_response_no_run_displayname_run3_summary_metrics = json.dumps(
    {
        "table": {
            "_type": "table-file",
            "artifact_path": "wandb-client-artifact://1122334455/test_results.table.json",
        },
    }
)

workspace_response_no_run_displayname = {
    "project_518fa79465d8ffaeb91015dce87e092f": {
        **fwb.project_payload,  # type: ignore
        "runs_c1233b7003317090ab5e2a75db4ad965": {
            "edges": [
                {
                    "node": {
                        **fwb.run_payload,  # type: ignore
                        "summaryMetricsSubset": workspace_response_no_run_displayname_run1_summary_metrics,
                        "summaryMetrics": workspace_response_no_run_displayname_run1_summary_metrics,
                    },
                },
                {
                    "node": {
                        **fwb.run2_payload,  # type: ignore
                        "summaryMetricsSubset": json.dumps({}),
                        "summaryMetrics": json.dumps({}),
                    },
                },
                {
                    "node": {
                        **fwb.run3_payload,  # type: ignore
                        "summaryMetricsSubset": workspace_response_no_run_displayname_run3_summary_metrics,
                        "summaryMetrics": workspace_response_no_run_displayname_run3_summary_metrics,
                    },
                },
            ]
        },
    }
}


empty_workspace_response = {
    "project_518fa79465d8ffaeb91015dce87e092f": {
        **fwb.project_payload,  # type: ignore
        "runs_c1233b7003317090ab5e2a75db4ad965": {"edges": []},
    }
}

workspace_response_filtered_run1_summary_metrics = json.dumps(
    {
        "table": {
            "_type": "table-file",
            "artifact_path": "wandb-client-artifact://1234567890/test_results.table.json",
        }
    }
)

workspace_response_filtered = {
    "project_518fa79465d8ffaeb91015dce87e092f": {
        **fwb.project_payload,  # type: ignore
        "runs_261949318143369aa6c158af92afee03": {
            "edges": [
                {
                    "node": {
                        **fwb.run_payload,  # type: ignore
                        "summaryMetricsSubset": workspace_response_filtered_run1_summary_metrics,
                        "summaryMetrics": workspace_response_filtered_run1_summary_metrics,
                        "displayName": "amber-glade-100",
                    }
                },
            ]
        },
    }
}

project_run_artifact_response = {
    "project_518fa79465d8ffaeb91015dce87e092f": {
        **fwb.project_payload,  # type: ignore
        "runs_c1233b7003317090ab5e2a75db4ad965": {
            "edges": [
                {
                    "node": {
                        **fwb.run_payload,  # type: ignore
                        "outputArtifacts_c1233b7003317090ab5e2a75db4ad965": {
                            "edges": [
                                {
                                    "node": {
                                        "id": "QXJ0aWZhY3Q6MTQyNTg4OTM=",
                                        "versionIndex": 0,
                                        "artifactSequence": fwb.artifactSequence_payload,
                                    }
                                }
                            ]
                        },
                    }
                }
            ]
        },
    }
}

artifact_version_sdk_response = {
    "artifact": {
        **fwb.artifactVersion_payload,  # type: ignore
        "state": "COMMITTED",
        "commitHash": "303db33c9f9264768626",
        "artifactType": fwb.defaultArtifactType_payload,
        "artifactSequence": {
            **fwb.artifactSequence_payload,
            "project": fwb.project_payload,
            "state": "READY",
        },  # type: ignore
    }
}


@pytest.mark.parametrize(
    "table_file_node_fn, mock_response",
    [
        # Path used in weave demos
        (
            (
                lambda: ops.project("stacey", "mendeleev")
                .artifactType("test_results")
                .artifacts()[0]
                .versions()[0]
                .file("test_results.table.json")
            ),
            file_path_response,
        ),
        # Path used in artifact browser
        (
            (
                lambda: ops.project("stacey", "mendeleev")
                .artifact("test_res_1fwmcd3q")
                .membershipForAlias("v0")
                .artifactVersion()
                .file("test_results.table.json")
            ),
            artifact_browser_response,
        ),
    ],
)
def test_table_call(table_file_node_fn, mock_response, fake_wandb):
    fake_wandb.fake_api.add_mock(lambda q, ndx: mock_response)
    table_file_node = table_file_node_fn()
    table_image0_node = table_file_node.table().rows()[0]["image"]
    table_image0 = weave.use(table_image0_node)
    assert table_image0.height == 299
    assert table_image0.width == 299
    assert table_image0.path == "media/images/6274b7484d7ed4b6ad1b.png"


def test_avfile_type(fake_wandb):
    fake_wandb.fake_api.add_mock(lambda q, ndx: file_path_response)
    f = (
        ops.project("stacey", "mendeleev")
        .artifactType("test_results")
        .artifacts()[0]
        .versions()[0]
        .file("test_results.table.json")
    )
    t = weavejs_ops.file_type(f)
    assert TaggedValueType(
        types.TypedDict(property_types={"project": wdt.ProjectType}),
        artifact_fs.FilesystemArtifactFileType(
            extension=types.Const(types.String(), "json"),
            wbObjectType=ops.TableType(),
        ),
    ).assign_type(weave.use(t))


def test_table_col_order_and_unknown_types(fake_wandb):
    fake_wandb.fake_api.add_mock(lambda q, ndx: file_path_response)
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
    fake_wandb.fake_api.add_mock(lambda q, ndx: file_path_response)
    node = (
        ops.project("stacey", "mendeleev")
        .artifactType("test_results")
        .artifacts()[0]
        .versions()[0]
        .file("does_not_exist")
    )
    assert weave.use(node) == None


def test_missing_file_no_entity(fake_wandb):
    fake_wandb.fake_api.add_mock(lambda q, ndx: file_path_no_entity_response)
    node = (
        ops.project("stacey", "mendeleev")
        .artifactType("test_results")
        .artifacts()[0]
        .versions()[0]
        .file("does_not_exist")
    )
    assert weave.use(node) == None


def table_mock1(q, ndx):
    if q["gql"].definitions[0].name.value == "WeavePythonCG":
        return workspace_response()
    else:
        return artifact_version_sdk_response


def table_mock1_no_display_name(q, ndx):
    if q["gql"].definitions[0].name.value == "WeavePythonCG":
        return workspace_response(False)
    else:
        return artifact_version_sdk_response


def table_mock2(q, ndx):
    if q["gql"].definitions[0].name.value == "WeavePythonCG":
        return workspace_response()
    else:
        return artifact_version_sdk_response


def table_mock_empty_workspace(q, ndx):
    if q["gql"].definitions[0].name.value == "WeavePythonCG":
        return empty_workspace_response


def test_map_gql_op(fake_wandb):
    fake_wandb.fake_api.add_mock(lambda q, ndx: project_run_artifact_response)
    node = (
        ops.project("stacey", "mendeleev")
        .runs()
        .limit(1)
        .loggedArtifactVersions()
        .limit(1)[0][0]
        .name()
    )
    assert weave.use(node) == "test_res_1fwmcd3q:v0"


def test_legacy_run_file_table_format(fake_wandb, cache_mode_minimal):
    fake_wandb.fake_api.add_mock(table_mock1)
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


def test_mapped_table_empty(fake_wandb, cache_mode_minimal):
    fake_wandb.fake_api.add_mock(table_mock_empty_workspace)
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
    assert weave.use(cell_node.indexCheckpoint()) == None
    assert weave.use(cell_node.run().name()) == None
    assert weave.use(cell_node.project().name()) == "mendeleev"


def test_mapped_table_tags(fake_wandb, cache_mode_minimal):
    fake_wandb.fake_api.add_mock(table_mock1)
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
    fake_wandb.fake_api.add_mock(table_mock1)
    cell_node = (
        ops.project("stacey", "mendeleev")
        .runs()
        .limit(10)[0]
        .summary()["table"]
        .table()
        .rows()
        .createIndexCheckpointTag()[5]["score_Amphibia"]
    )
    assert weave.use(cell_node.indexCheckpoint()) == 5
    assert weave.use(cell_node.run().name()) == "amber-glade-100"
    assert weave.use(cell_node.project().name()) == "mendeleev"


def test_workspace_table_type(fake_wandb):
    fake_wandb.fake_api.add_mock(table_mock2)
    summary_node = ops.project("stacey", "mendeleev").runs().summary()
    cell_node = summary_node["table"].table()
    assert TaggedValueType(
        types.TypedDict(property_types={"project": wdt.ProjectType}),
        types.List(
            object_type=types.optional(
                TaggedValueType(
                    types.TypedDict(property_types={"run": wdt.RunType}),
                    types.optional(ops.TableType()),
                )
            )
        ),
    ).assign_type(cell_node.type)


def test_workspace_table_rows_type(fake_wandb):
    fake_wandb.fake_api.add_mock(table_mock2)
    cell_node = (
        ops.project("stacey", "mendeleev").runs().summary()["table"].table().rows()
    )
    assert TaggedValueType(
        types.TypedDict(property_types={"project": wdt.ProjectType}),
        types.List(
            object_type=types.optional(
                TaggedValueType(
                    types.TypedDict(property_types={"run": wdt.RunType}),
                    ops.ArrowWeaveListType(
                        object_type=types.TypedDict(
                            property_types={
                                "id": types.optional(types.String()),
                                "image": types.optional(
                                    ops.ImageArtifactFileRef.WeaveType()
                                ),
                                "guess": types.optional(types.String()),
                                "truth": types.optional(types.String()),
                                "score_Animalia": types.optional(types.Number()),
                                "score_Amphibia": types.optional(types.Number()),
                                "score_Arachnida": types.optional(types.Number()),
                                "score_Aves": types.optional(types.Number()),
                                "score_Fungi": types.optional(types.Number()),
                                "score_Insecta": types.optional(types.Number()),
                                "score_Mammalia": types.optional(types.Number()),
                                "score_Mollusca": types.optional(types.Number()),
                                "score_Plantae": types.optional(types.Number()),
                                "score_Reptilia": types.optional(types.Number()),
                            }
                        )
                    ),
                )
            )
        ),
    ).assign_type(cell_node.type)


def test_table_tags_column_first(fake_wandb):
    fake_wandb.fake_api.add_mock(table_mock1)
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
    fake_wandb.fake_api.add_mock(table_mock2)
    # Query 1:
    project_node = ops.project("stacey", "mendeleev")
    project_runs_node = project_node.runs().limit(1)
    summary_node = project_runs_node.summary()
    # this use is important as it models the sequence of calls in UI
    # and invokes the issues with artifact paths
    assert list(weave.use(summary_node)[0].keys()) == ["table", "legacy_table", "image"]

    # Query 2:
    table_rows_node = summary_node.pick("table").table().rows()
    assert len(weave.use(table_rows_node)) == 1


def table_mock_filtered(q, ndx):
    if q["gql"].definitions[0].name.value == "WeavePythonCG":
        return workspace_response_filtered
    else:
        return artifact_version_sdk_response


def test_tag_run_color_lookup(fake_wandb):
    fake_wandb.fake_api.add_mock(table_mock_filtered)
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
    fake_wandb.fake_api.add_mock(
        lambda q, ndx: {
            "project_518fa79465d8ffaeb91015dce87e092f": {
                **fwb.project_payload,
                "artifactType_46d22fef09db004187bb8da4b5e98c58": {
                    **fwb.defaultArtifactType_payload,
                    "artifactCollections_c1233b7003317090ab5e2a75db4ad965": {
                        "edges": [
                            {
                                "node": {
                                    **fwb.artifactSequence_payload,
                                    "artifacts_c1233b7003317090ab5e2a75db4ad965": {
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


def test_domain_gql_through_dicts_with_fn_nodes(fake_wandb, cache_mode_minimal):
    fake_wandb.fake_api.add_mock(lambda q, ndx: workspace_response())
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
        "run_names": [
            {"name": "amber-glade-100"},
            {"name": "run2-display_name"},
            {"name": "run3-display_name"},
        ],
    }


def test_domain_gql_around_fn_nodes(fake_wandb):
    fake_wandb.fake_api.add_mock(lambda q, ndx: workspace_response())
    project_node = ops.project("stacey", "mendeleev")
    runs_node = project_node.runs()
    sorted_runs = runs_node.sort(lambda row: ops.make_list(a=row.createdAt()), ["asc"])
    names_node = sorted_runs.name()

    p = stitch.stitch([names_node])
    obj_recorder = p.get_result(runs_node)
    assert len(obj_recorder.calls) == 2


def test_lambda_gql_stitch(fake_wandb):
    fake_wandb.fake_api.add_mock(
        lambda q, ndx: {"project_518fa79465d8ffaeb91015dce87e092f": fwb.project_payload}
    )
    weave.use(
        ops.make_list(a="a", b="b", c="c").map(
            lambda x: x + ops.project("stacey", "mendeleev").name()
        )
    ) == None


def test_arrow_groupby_nested_tag_stripping(fake_wandb):
    fake_wandb.fake_api.add_mock(lambda q, ndx: file_path_response)
    groupby_node = (
        ops.project("stacey", "mendeleev")
        .artifactType("test_results")
        .artifacts()[0]
        .versions()[0]
        .file("test_results.table.json")
        .table()
        .rows()
        .createIndexCheckpointTag()
        .groupby(lambda row: ops.dict_(x=row["truth"]))[0]["truth"]
    )
    grouped = weave.use(groupby_node)
    assert len(grouped) == 50


def test_arrow_groupby_sort(fake_wandb):
    fake_wandb.fake_api.add_mock(lambda q, ndx: file_path_response)
    groupby_node = (
        ops.project("stacey", "mendeleev")
        .artifactType("test_results")
        .artifacts()[0]
        .versions()[0]
        .file("test_results.table.json")
        .table()
        .rows()
        .createIndexCheckpointTag()
        .groupby(lambda row: ops.dict_(x=row["truth"]))
        .sort(lambda row: ops.make_list(a=row.groupkey()["x"]), ["desc"])[0]
        .groupkey()["x"]
    )
    grouped = weave.use(groupby_node)
    assert grouped == "Reptilia"


def test_arrow_tag_stripping(fake_wandb):
    fake_wandb.fake_api.add_mock(lambda q, ndx: file_path_response)
    awl_node = (
        ops.project("stacey", "mendeleev")
        .artifactType("test_results")
        .artifacts()[0]
        .versions()[0]
        .file("test_results.table.json")
        .table()
        .rows()
        .createIndexCheckpointTag()
    )
    awl = weave.use(awl_node)
    tag_stripped = awl._arrow_data_asarray_no_tags()
    assert tag_stripped.type[0].name != "_tag"


def test_arrow_tag_serialization_can_handle_runs_in_concat(fake_wandb):
    fake_wandb.fake_api.add_mock(table_mock_filtered)
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
    concatted = arrow.ops.concat(arr=concatted_list)

    # now get the run from the tags
    weave.use(ops.run_ops.run_tag_getter_op(concatted[0]))


@pytest.mark.skip(reason="This test requires communcation with wandb.ai")
def test_shawn_groupby_profiling_correctness():
    x = (
        ops.project("shawn", "dsviz-simple-tables")
        .artifact("simple_tables")
        .membershipForAlias("v5")
        .artifactVersion()
        .file("my-table.table.json")
        .table()
        .rows()
        .createIndexCheckpointTag()
        .groupby(lambda row: ops.dict_(x=row["x"]))[0]["c"]
    )

    cProfile.runctx(
        "weave.use(x)",
        globals(),
        locals(),
        filename="groupby-dsviz-simple-tables.pstat",
    )

    assert len(weave.use(x)) == 66311


def test_loading_artifact_browser_request_1(fake_wandb):
    # Leaf 1: Get's the current artifact collection
    fake_wandb.fake_api.add_mock(
        lambda q, ndx: {
            "project_518fa79465d8ffaeb91015dce87e092f": {
                **fwb.project_payload,  # type: ignore
                "artifactCollection_d651817074b6a8074e87e9dfd5767726": {
                    **fwb.artifactSequence_payload,  # type: ignore
                },
            }
        }
    )
    ac_node = ops.project("stacey", "mendeleev").artifact("test_res_1fwmcd3q")
    assert weave.use(ac_node) != None


def test_loading_artifact_browser_request_2(fake_wandb, cache_mode_minimal):
    ac_node = ops.project("stacey", "mendeleev").artifact("test_res_1fwmcd3q")
    # Leaf 2: Get collection details
    fake_wandb.fake_api.add_mock(
        lambda q, ndx: {
            "project_518fa79465d8ffaeb91015dce87e092f": {
                **fwb.project_payload,  # type: ignore
                "artifactCollection_d651817074b6a8074e87e9dfd5767726": {
                    **fwb.artifactSequence_payload,  # type: ignore
                    "__typename": "ArtifactSequence",
                    "project": fwb.project_payload,
                    "artifacts_c1233b7003317090ab5e2a75db4ad965": {
                        "edges": [{"node": {**fwb.artifactVersion_payload}}]
                    },
                    "artifactMembership_fe9cc269bee939ccb54ebba88c6087dd": {
                        **fwb.artifactMembership_payload
                    },
                    "artifactMemberships_first_1": {
                        "edges": [
                            {
                                "node": {
                                    **fwb.artifactMembership_payload,
                                    "aliases": [fwb.artifactAlias_payload],
                                }
                            }
                        ]
                    },
                    "artifactMemberships": {
                        "edges": [
                            {
                                "node": {
                                    **fwb.artifactMembership_payload,
                                    "aliases": [fwb.artifactAlias_payload],
                                }
                            }
                        ]
                    },
                },
            }
        }
    )
    ac_detail_node = dict_(
        **{
            "name": ac_node.name(),
            "isPortfolio": ac_node.isPortfolio(),
            "versionCount": ac_node.versions().count(),
            "latestVersionIndex": ac_node.lastMembership().versionIndex(),
            "projectName": ac_node.project().name(),
            "entityName": ac_node.project().entity().name(),
            "artifactTypeName": ac_node._get_op("type")().name(),
            "memberships": ac_node.memberships().map(
                lambda row: dict_(
                    **{
                        "versionIndex": row.versionIndex(),
                        "artifactVersion": row.artifactVersion(),
                        "aliases": row.aliases().alias(),
                    }
                )
            ),
        }
    )
    assert weave.use(ac_detail_node) != None

    # Leaf 3: Get the specific membership
    fake_wandb.fake_api.clear_mock_handlers()
    fake_wandb.fake_api.add_mock(
        lambda q, ndx: {
            "project_518fa79465d8ffaeb91015dce87e092f": {
                **fwb.project_payload,  # type: ignore
                "artifactCollection_d651817074b6a8074e87e9dfd5767726": {
                    **fwb.artifactSequence_payload,  # type: ignore
                    "artifactMembership_78e7a3fd51159b4fdfb0815be0b0f92c": {
                        **fwb.artifactMembership_payload
                    },
                },
            }
        }
    )
    mem_node = ac_node.membershipForAlias("v0")
    assert weave.use(mem_node) != None

    # Leaf 4: Get the specific membership details
    fake_wandb.fake_api.clear_mock_handlers()
    fake_wandb.fake_api.add_mock(
        lambda q, ndx: {
            "project_518fa79465d8ffaeb91015dce87e092f": {
                **fwb.project_payload,  # type: ignore
                "artifactCollection_d651817074b6a8074e87e9dfd5767726": {
                    **fwb.artifactSequence_payload,  # type: ignore
                    "artifactMembership_78e7a3fd51159b4fdfb0815be0b0f92c": {
                        **fwb.artifactMembership_payload
                    },
                },
            }
        }
    )
    mem_detail_node = dict_(
        **{
            "versionIndex": mem_node.versionIndex(),
            "artifactVersionId": mem_node.artifactVersion().id(),
        }
    )
    assert weave.use(mem_detail_node) != None


def test_loading_artifact_browser_request_3(fake_wandb, cache_mode_minimal):
    ac_node = ops.project("stacey", "mendeleev").artifact("test_res_1fwmcd3q")
    mem_node = ac_node.membershipForAlias("v0")
    # Leaf 5: Get the specific artifact version details
    fake_wandb.fake_api.add_mock(
        lambda q, ndx: {
            "project_518fa79465d8ffaeb91015dce87e092f": {
                **fwb.project_payload,  # type: ignore
                "artifactCollection_d651817074b6a8074e87e9dfd5767726": {
                    **fwb.artifactSequence_payload,  # type: ignore
                    "artifactMembership_78e7a3fd51159b4fdfb0815be0b0f92c": {
                        **fwb.artifactMembership_payload,  # type: ignore
                        "artifact": {
                            **fwb.artifactVersion_payload,  # type: ignore
                            "description": "",
                            "digest": "51560154fe3bae863d18335d39129732",
                            "commitHash": "303db33c9f9264768626",
                            "createdAt": "2021-07-10T19:27:32",
                            "usedBy": {
                                "edges": [
                                    {
                                        "node": {
                                            **fwb.run_payload,  # type: ignore
                                        }
                                    }
                                ]
                            },
                            "size": 90574246,
                            "artifactCollections": {
                                "edges": [
                                    {
                                        "node": {
                                            **fwb.artifactSequence_payload,  # type: ignore
                                            "__typename": "ArtifactSequence",
                                            "project": {
                                                **fwb.project_payload,  # type: ignore
                                            },
                                        }
                                    }
                                ]
                            },
                            "createdBy": {
                                "__typename": "Run",
                                **fwb.run_payload,  # type: ignore
                                "inputArtifacts_c1233b7003317090ab5e2a75db4ad965": {
                                    "edges": [
                                        {
                                            "node": {
                                                **fwb.artifactVersion_payload,  # type: ignore
                                                "artifactSequence": {
                                                    **fwb.artifactSequence_payload,  # type: ignore
                                                    "project": {
                                                        **fwb.project_payload,  # type: ignore
                                                    },
                                                },
                                                "artifactType": {
                                                    **fwb.defaultArtifactType_payload,  # type: ignore
                                                },
                                            },
                                        }
                                    ]
                                },
                            },
                        },
                        "artifactCollection": {
                            **fwb.artifactSequence_payload,  # type: ignore
                            "aliases": {
                                "edges": [
                                    {
                                        "node": {
                                            **fwb.artifactAlias_payload,  # type: ignore
                                        }
                                    }
                                ]
                            },
                            "project": {
                                **fwb.project_payload,  # type: ignore
                                "entity": {
                                    **fwb.entity_payload,  # type: ignore
                                    "artifactCollections_c96697489c051b1be46673088f743964": {
                                        "edges": [
                                            {
                                                "node": {
                                                    **fwb.artifactSequence_payload,  # type: ignore
                                                }
                                            }
                                        ]
                                    },
                                },
                            },
                            "__typename": "ArtifactSequence",
                            "artifactMemberships": {
                                "edges": [
                                    {
                                        "node": {
                                            **fwb.artifactMembership_payload,  # type: ignore
                                            "aliases": [
                                                {
                                                    **fwb.artifactAlias_payload,  # type: ignore
                                                },
                                            ],
                                        }
                                    }
                                ]
                            },
                        },
                    },
                },
            }
        }
    )
    av_node = mem_node.artifactVersion()
    mem_collection_node = mem_node.collection()
    av_details_node = dict_(
        **{
            "id": av_node.id(),
            "colId": mem_collection_node.id(),
            "colAliases": mem_collection_node.aliases().alias(),
            "colTypeName": mem_collection_node._get_op("type")().name(),
            "colEntityName": mem_collection_node.project().entity().name(),
            "colProjectName": mem_collection_node.project().name(),
            "colName": mem_collection_node.name(),
            "memVersionIndex": mem_node.versionIndex(),
            "description": av_node.description(),
            "digest": av_node.digest(),
            "createdAt": av_node.createdAt(),
            "usedByCount": av_node.usedBy().count(),
            "fileCount": av_node.files().count(),
            "size": av_node.size(),
            "isPortfolio": mem_collection_node.isPortfolio(),
            "memberships": mem_collection_node.memberships().map(
                lambda row: dict_(
                    **{
                        "versionIndex": row.versionIndex(),
                        "aliases": row.aliases().alias(),
                    }
                )
            ),
            "filteredCollections": av_node.artifactCollections()
            .filter(lambda row: row.isPortfolio())
            .map(
                lambda row: dict_(
                    **{
                        "name": row._get_op("name")(),
                        "typeName": row._get_op("type")().name(),
                        "entityName": row.project().entity().name(),
                        "projectName": row.project().name(),
                    }
                )
            ),
            "dependencies": av_node.createdBy()
            .usedArtifactVersions()
            .map(
                lambda row: dict_(
                    **{
                        "name": row._get_op("name")(),
                        "typeName": row.artifactType().name(),
                        "entityName": row.artifactSequence().project().entity().name(),
                        "projectName": row.artifactSequence().project().name(),
                    }
                )
            ),
            "hasPortfolios": mem_collection_node.project()
            .entity()
            .portfolios()
            .filter(
                lambda row: row._get_op("type")().name()
                == mem_collection_node._get_op("type")().name()
            )
            .count()
            >= 1,
        }
    )
    assert weave.use(av_details_node) != None

    # Leaf 6: Get Portfolios
    fake_wandb.fake_api.clear_mock_handlers()
    fake_wandb.fake_api.add_mock(
        lambda q, ndx: {
            "project_518fa79465d8ffaeb91015dce87e092f": {
                **fwb.project_payload,  # type: ignore
                "artifactCollection_d651817074b6a8074e87e9dfd5767726": {
                    **fwb.artifactSequence_payload,  # type: ignore
                    "artifactMembership_78e7a3fd51159b4fdfb0815be0b0f92c": {
                        **fwb.artifactMembership_payload,  # type: ignore
                        "artifact": {
                            **fwb.artifactVersion_payload,  # type: ignore
                            "artifactMemberships": {
                                "edges": [
                                    {
                                        "node": {
                                            **fwb.artifactMembership_payload,  # type: ignore
                                            "artifactCollection": {
                                                **fwb.artifactSequence_payload,  # type: ignore
                                                "__typename": "ArtifactSequence",
                                            },
                                        }
                                    }
                                ]
                            },
                        },
                    },
                },
            }
        }
    )
    portfolios_node = (
        av_node.memberships().filter(lambda row: row.collection().isPortfolio()).count()
    )
    assert weave.use(portfolios_node) != None

    # Leaf 7: Is Weave
    fake_wandb.fake_api.clear_mock_handlers()
    fake_wandb.fake_api.add_mock(
        lambda q, ndx: {
            "project_518fa79465d8ffaeb91015dce87e092f": {
                **fwb.project_payload,  # type: ignore
                "artifactCollection_d651817074b6a8074e87e9dfd5767726": {
                    **fwb.artifactSequence_payload,  # type: ignore
                    "artifactMembership_78e7a3fd51159b4fdfb0815be0b0f92c": {
                        **fwb.artifactMembership_payload,  # type: ignore
                        "artifact": {
                            **fwb.artifactVersion_payload,  # type: ignore
                        },
                    },
                },
            }
        }
    )
    is_weave_node = av_node.isWeaveObject()
    assert weave.use(is_weave_node) != None


example_history = [
    '{"_step":0,"loss":0.9416526556015015,"_runtime":247,"accuracy":0.7200000286102295,"epoch":0,"val_accuracy":0.7530242204666138,"_timestamp":1625961050,"val_loss":0.7652576565742493}',
    '{"_step":1,"predictions_10K":{"nrows":1000,"path":"media/table/predictions_10K_1_661a2d7d82a08afe8583.table.json","sha256":"661a2d7d82a08afe858320cc73ff3ac3ff3e5915a958c02e765963409d4716e9","size":147790,"_type":"table-file","artifact_path":"wandb-artifact://41727469666163743a3134323538383933/predictions_10K.table.json","ncols":14},"_runtime":294,"_timestamp":1625961097}',
    '{"_step":2,"loss":0.6638407707214355,"_runtime":545,"accuracy":0.7916250228881836,"epoch":1,"val_accuracy":0.7641128897666931,"_timestamp":1625961348,"val_loss":0.7551828622817993}',
    '{"_step":3,"predictions_10K":{"size":146810,"_type":"table-file","artifact_path":"wandb-artifact://41727469666163743a3134323539373631/predictions_10K.table.json","ncols":14,"nrows":1000,"path":"media/table/predictions_10K_3_3247b2550f0007cbaa5f.table.json","sha256":"3247b2550f0007cbaa5f3ad934d5d16bcbf966bcfc2770eb1e98e03b78b671fe"},"_runtime":591,"_timestamp":1625961394}',
    '{"_step":4,"loss":0.6015360951423645,"_runtime":824,"accuracy":0.8076249957084656,"epoch":2,"val_accuracy":0.7560483813285828,"_timestamp":1625961627,"val_loss":0.7426469326019287}',
    '{"_step":5,"predictions_10K":{"nrows":1000,"path":"media/table/predictions_10K_5_fa5fdbb0e0e48b873473.table.json","sha256":"fa5fdbb0e0e48b8734733a6a8bd2f460dfc3de35c1fedba5f0ac97eb9438ac17","size":146138,"_type":"table-file","artifact_path":"wandb-artifact://41727469666163743a3134323630353439/predictions_10K.table.json","ncols":14},"_runtime":870,"_timestamp":1625961673}',
    '{"_step":6,"loss":0.5667485594749451,"_runtime":1103,"accuracy":0.8165000081062317,"epoch":3,"val_accuracy":0.7752016186714172,"_timestamp":1625961906,"val_loss":0.7002165913581848}',
    '{"_step":7,"predictions_10K":{"ncols":14,"nrows":1000,"path":"media/table/predictions_10K_7_674d715bcfebaf8cc33e.table.json","sha256":"674d715bcfebaf8cc33ec920791498cae6321da393cc4bb8e44fd487eca4fedf","size":144151,"_type":"table-file","artifact_path":"wandb-artifact://41727469666163743a3134323631353532/predictions_10K.table.json"},"_runtime":1150,"_timestamp":1625961953}',
    '{"_step":8,"loss":0.5219206809997559,"_runtime":1383,"accuracy":0.8242499828338623,"epoch":4,"val_accuracy":0.78125,"_timestamp":1625962186,"val_loss":0.6415265202522278}',
    '{"_step":9,"predictions_10K":{"ncols":14,"nrows":1000,"path":"media/table/predictions_10K_9_fb0f1f25a0be1a907ec0.table.json","sha256":"fb0f1f25a0be1a907ec0c88efb482078736a40e49055e5251e42a368c12c9b2a","size":144982,"_type":"table-file","artifact_path":"wandb-artifact://41727469666163743a3134323632393738/predictions_10K.table.json"},"_runtime":1427,"_timestamp":1625962230}',
]
example_history_keys = {
    "sets": [],
    "keys": {
        "_step": {
            "typeCounts": [{"type": "number", "count": 10}],
            "monotonic": True,
            "previousValue": 9,
        },
        "_runtime": {
            "typeCounts": [{"type": "number", "count": 10}],
            "monotonic": True,
            "previousValue": 1427,
        },
        "_timestamp": {
            "typeCounts": [{"type": "number", "count": 10}],
            "monotonic": True,
            "previousValue": 1625962230,
        },
        "epoch": {
            "typeCounts": [{"type": "number", "count": 5}],
            "monotonic": True,
            "previousValue": 4,
        },
        "predictions_10K": {
            "typeCounts": [{"type": "table-file", "count": 5}],
            "monotonic": True,
            "previousValue": -1.7976931348623157e308,
        },
    },
    "lastStep": 9,
}

history_keys_with_media = {
    "sets": [],
    "keys": {
        "metric2": {
            "typeCounts": [{"type": "number", "count": 1001}],
            "previousValue": 1.6397776348651e06,
        },
        "_step": {
            "typeCounts": [{"type": "number", "count": 1001}],
            "monotonic": True,
            "previousValue": 1000,
        },
        "_runtime": {
            "typeCounts": [{"type": "number", "count": 1001}],
            "monotonic": True,
            "previousValue": 791.536298751831,
        },
        "_timestamp": {
            "typeCounts": [{"type": "number", "count": 1001}],
            "monotonic": True,
            "previousValue": 1.68322130708908e09,
        },
        "img": {
            "typeCounts": [
                {
                    "type": "image-file",
                    "count": 1001,
                    "keys": {
                        "boxes": [
                            {
                                "type": "map",
                                "keys": {
                                    "predictions": [
                                        {
                                            "type": "boxes2D",
                                            "keys": {
                                                "size": [{"type": "number"}],
                                                "_type": [{"type": "string"}],
                                                "sha256": [{"type": "string"}],
                                                "path": [{"type": "string"}],
                                            },
                                        }
                                    ]
                                },
                            }
                        ]
                    },
                    "nestedTypes": ["default"],
                }
            ],
            "monotonic": True,
            "previousValue": -1.7976931348623157e308,
        },
    },
    "lastStep": 1000,
}


def run_history_mocker(q, ndx):
    query_str = q["gql"].loc.source.body
    if "artifact" in query_str:
        return artifact_version_sdk_response

    node = {
        **fwb.run_payload,  # type: ignore
    }

    if "sampledParquetHistory" in query_str:
        node["sampledParquetHistory"] = {
            "parquetUrls": ["https://api.wandb.test/test.parquet"],
            "liveData": [
                json.loads(s)
                for s in [
                    '{"_step":8,"loss":0.5219206809997559,"_runtime":1383,"accuracy":0.8242499828338623,"epoch":4,"val_accuracy":0.78125,"_timestamp":1625962186,"val_loss":0.6415265202522278}',
                    '{"_step":9,"predictions_10K":{"ncols":14,"nrows":1000,"path":"media/table/predictions_10K_9_fb0f1f25a0be1a907ec0.table.json","sha256":"fb0f1f25a0be1a907ec0c88efb482078736a40e49055e5251e42a368c12c9b2a","size":144982,"_type":"table-file","artifact_path":"wandb-artifact://41727469666163743a3134323632393738/predictions_10K.table.json"},"_runtime":1427,"_timestamp":1625962230}',
                ]
            ],
        }

    if "historyKeys" in query_str:
        node["historyKeys"] = example_history_keys

    return {
        "project_518fa79465d8ffaeb91015dce87e092f": {
            **fwb.project_payload,  # type: ignore
            "runs_c1233b7003317090ab5e2a75db4ad965": {"edges": [{"node": node}]},
        }
    }


def run_history_mocker_with_pq_media(q, ndx):
    query_str = q["gql"].loc.source.body
    if "artifact" in query_str:
        return artifact_version_sdk_response

    node = {
        **fwb.run_payload,  # type: ignore
    }

    if "sampledParquetHistory" in query_str:
        node["sampledParquetHistory"] = {
            "parquetUrls": ["https://api.wandb.test/test_media.parquet"],
            "liveData": [
                {
                    "metric2": 1639777.6348651,
                    "_timestamp": 1683221307.0890799,
                    "_step": 1000.0,
                    "_runtime": 791.536298751831,
                    "img": {
                        "size": 3151148.0,
                        "height": 1024.0,
                        "width": 1024.0,
                        "_type": "image-file",
                        "format": "png",
                        "boxes": {
                            "predictions": {
                                "path": "media/metadata/boxes2D/img_999_7d232aa991dca7a6e3c5.boxes2D.json",
                                "size": 551.0,
                                "_type": "boxes2D",
                                "sha256": "7d232aa991dca7a6e3c5cd18acc3d3c7da1a865eb6b135f6c9f7af966b9fdfdb",
                            }
                        },
                        "path": "media/images/img_999_051320f86e77a481d041.png",
                        "sha256": "051320f86e77a481d041cd317fd2ab66925a2db8218c5e0c6fb61d740f24e8b5",
                    },
                }
            ],
        }

    if "historyKeys" in query_str:
        node["historyKeys"] = history_keys_with_media

    return {
        "project_518fa79465d8ffaeb91015dce87e092f": {
            **fwb.project_payload,  # type: ignore
            "runs_c1233b7003317090ab5e2a75db4ad965": {"edges": [{"node": node}]},
        }
    }


def test_run_history(fake_wandb):
    fake_wandb.fake_api.add_mock(run_history_mocker)
    node = ops.project("stacey", "mendeleev").runs()[0].history()
    assert isinstance(node.type, TaggedValueType)
    assert types.List(
        types.TypedDict(
            {
                "_step": types.Number(),
                # we no longer send back system metrics
                # "system/gpu.0.powerWatts": types.optional(types.Number()),
                "epoch": types.optional(types.Number()),
                "predictions_10K": types.optional(
                    artifact_fs.FilesystemArtifactFileType(
                        types.Const(types.String(), "json"), table.TableType()
                    ),
                ),
            }
        )
    ).assign_type(node.type.value)

    # this should just return dummy history
    assert weave.use(node) == [{"_step": i} for i in range(10)]

    # now we'll fetch a just one of the columns
    new_node = node["epoch"]
    assert types.List(
        types.optional(types.Number()),
    ).assign_type(new_node.type.value)
    assert weave.use(new_node) == [0, None, 1, None, 2, None, 3, None, 4, None]

    # now we'll create a graph that fetches two columns and execute it
    epoch_node = node["epoch"]
    pred_node = node["predictions_10K"]
    assert types.List(
        types.optional(
            artifact_fs.FilesystemArtifactFileType(
                types.Const(types.String(), "json"), table.TableType()
            ),
        )
    ).assign_type(pred_node.type.value)

    # simulates what a table call would do, selecting multiple columns
    result = weave.use([epoch_node, pred_node])
    assert len(result) == 2

    # check the types, result lengths
    assert all(len(r) == 10 for r in result)
    assert all(r == None or isinstance(r, (int, float)) for r in result[0])
    assert all(
        r == None or isinstance(r, artifact_fs.FilesystemArtifactFile)
        for r in result[1]
    )


def test_run_history_2(fake_wandb):
    fake_wandb.fake_api.add_mock(run_history_mocker)
    node = ops.project("stacey", "mendeleev").runs()[0].history2()
    assert isinstance(node.type, TaggedValueType)
    assert ArrowWeaveListType(
        types.TypedDict(
            {
                "_step": types.Number(),
                # we no longer send back system metrics
                # "system/gpu.0.powerWatts": types.optional(types.Number()),
                "epoch": types.optional(types.Number()),
                "predictions_10K": types.optional(
                    artifact_fs.FilesystemArtifactFileType(
                        types.Const(types.String(), "json"), table.TableType()
                    ),
                ),
            }
        )
    ).assign_type(node.type.value)

    # this should just return dummy history
    assert weave.use(node).to_pylist_raw() == [{"_step": i} for i in range(10)]

    # now we'll fetch a just one of the columns
    new_node = node["epoch"]
    assert ArrowWeaveListType(
        types.optional(types.Number()),
    ).assign_type(new_node.type.value)
    assert weave.use(new_node).to_pylist_raw() == [
        0,
        None,
        1,
        None,
        2,
        None,
        3,
        None,
        4,
        None,
    ]

    # now we'll create a graph that fetches all three columns and execute it
    epoch_node = node["epoch"]
    pred_node = node["_runtime"]
    table_node = node["predictions_10K"]
    assert types.List(types.optional(types.Number())).assign_type(pred_node.type.value)

    # simulates what a table call would do, selecting multiple columns
    result = weave.use([epoch_node, pred_node, table_node])
    assert len(result) == 3

    # check the types, result lengths
    assert all(len(r) == 10 for r in result)
    assert all(r == None or isinstance(r, (int, float)) for r in result[0])
    assert all(r == None or isinstance(r, (int, float)) for r in result[1])
    assert all(
        r == None or isinstance(r, artifact_fs.FilesystemArtifactFile)
        for r in result[2]
    )


def test_run_history2_media_types(fake_wandb, cache_mode_minimal):
    fake_wandb.fake_api.add_mock(run_history_mocker_with_pq_media)

    # this is actually from the launch-test/prodmon project, but mocked here as stacey/mendeleev
    node = ops.project("stacey", "mendeleev").runs()[0].history2()
    image_node = node["img"]
    metric2_node = node["metric2"]

    # simulates what a table call would do, selecting multiple columns
    result = weave.use([image_node, metric2_node])

    assert types.List(types.optional(wbmedia.ImageArtifactFileRefType())).assign_type(
        image_node.type
    )
    assert types.List(types.optional(types.Number())).assign_type(metric2_node.type)
    assert len(result) == 2
    assert len(result[0]) == 1001

    # check that parquet data is converted properly
    assert isinstance(result[0][0], wbmedia.ImageArtifactFileRef)

    # check that live data is converted properly
    last_img = result[0][len(result[0]) - 1]
    assert isinstance(last_img, wbmedia.ImageArtifactFileRef)
    assert last_img.boxes == {}
    assert last_img.masks == {}
    assert last_img.classes is None
    assert last_img.path == "media/images/img_999_051320f86e77a481d041.png"
    assert last_img.format == "png"
    assert last_img.width == 1024
    assert last_img.height == 1024
    assert (
        last_img.sha256
        == "051320f86e77a481d041cd317fd2ab66925a2db8218c5e0c6fb61d740f24e8b5"
    )


def run_history_as_of_mocker(q, ndx):
    return {
        "project_518fa79465d8ffaeb91015dce87e092f": {
            **fwb.project_payload,  # type: ignore
            "runs_c1233b7003317090ab5e2a75db4ad965": {
                "edges": [
                    {
                        "node": {
                            **fwb.run_payload,  # type: ignore
                            "history_c81e728d9d4c2f636f067f89cc14862c": [
                                example_history[2]
                            ],
                        }
                    }
                ]
            },
        }
    }


def test_run_history_as_of(fake_wandb):
    fake_wandb.fake_api.add_mock(run_history_as_of_mocker)
    node = ops.project("stacey", "mendeleev").runs()[0].historyAsOf(2)
    assert isinstance(node.type, TaggedValueType)
    assert types.TypedDict(
        {
            "_step": types.Number(),
            "_timestamp": types.Number(),
            "_runtime": types.Number(),
            "accuracy": types.Number(),
            "epoch": types.Number(),
            "loss": types.Number(),
            "val_accuracy": types.Number(),
            "val_loss": types.Number(),
        }
    ).assign_type(node.type.value)

    keys = ["_step", "_timestamp", "_runtime", "predictions_10K"]
    nodes = [node[key] for key in keys]

    assert weave.use(nodes) == [
        json.loads(example_history[2]).get(key, None) for key in keys
    ]


def test_artifact_membership_link(fake_wandb):
    fake_wandb.fake_api.add_mock(lambda q, ndx: artifact_browser_response)
    node = amo.artifact_membership_link(
        ops.project("stacey", "mendeleev")
        .artifact("test_res_1fwmcd3q")
        .membershipForAlias("v0")
    )

    assert weave.use(node) == wdt.Link(
        name="test_res_1fwmcd3q:v0",
        url="/stacey/mendeleev/artifacts/test_results/test_res_1fwmcd3q/v0",
    )


def test_run_colors(fake_wandb):
    fake_wandb.fake_api.add_mock(table_mock_filtered)
    colors_node = ops.dict_(
        **{"1ht5692d": "rgb(218, 76, 76)", "2ed5xwpn": "rgb(83, 135, 221)"}
    )
    node = (
        ops.project("stacey", "mendeleev")
        .filteredRuns("{}", "-createdAt")
        .limit(50)
        .summary()
        .pick("table")
        .table()
        .rows()
        .dropna()
        .concat()
        .map(
            lambda row: ops.dict_(
                color=colors_node.pick(row.run().id()), name=row.run().name()
            )
        )
        .index(0)
        .pick("color")
    )
    assert weave.use(node) == "rgb(83, 135, 221)"


def test_arrow_groupby_external_tag(fake_wandb):
    fake_wandb.fake_api.add_mock(table_mock_filtered)
    run_names = (
        ops.project("stacey", "mendeleev")
        .filteredRuns("{}", "-createdAt")
        .limit(50)
        .summary()
        .pick("table")
        .table()
        .rows()
        .dropna()
        .concat()
        .createIndexCheckpointTag()
        .groupby(lambda row: ops.dict_(x=row["truth"]))
        .sort(lambda row: ops.make_list(a=row.groupkey()["x"]), ["desc"])[0]
        .run()
        .name()[0]
    )
    run_names_res = weave.use(run_names)
    assert run_names_res == "amber-glade-100"


def test_join_all_tables(fake_wandb, cache_mode_minimal):
    fake_wandb.fake_api.add_mock(table_mock_filtered)
    joined_row = (
        ops.project("stacey", "mendeleev")
        .filteredRuns("{}", "-createdAt")
        .limit(50)
        .summary()
        .pick("table")
        .table()
        .rows()
        .dropna()
        .joinAll(lambda row: row["truth"], True)
        .createIndexCheckpointTag()[0]
    )
    run_names_res = weave.use(joined_row["score_Fungi"][0].run().name())
    assert run_names_res == "amber-glade-100"
    run_names_res = weave.use(joined_row["score_Fungi"][0].project().name())
    assert run_names_res == "mendeleev"


def test_arrow_unnest_shallow_tags(fake_wandb):
    fake_wandb.fake_api.add_mock(table_mock_filtered)
    x_val = (
        ops.project("stacey", "mendeleev")
        .filteredRuns("{}", "-createdAt")
        .limit(50)[0]
        .summary()
        .pick("table")
        .table()
        .rows()
        .map(lambda row: ops.dict_(x=row["truth"], y=row["guess"]))
        .unnest()[3]["x"]
    )
    run_name = x_val.run().name()


def test_arrow_unnest_deep_tags(fake_wandb):
    fake_wandb.fake_api.add_mock(table_mock_filtered)
    x_val = (
        ops.project("stacey", "mendeleev")
        .filteredRuns("{}", "-createdAt")
        .limit(50)
        .summary()
        .pick("table")
        .table()
        .rows()
        .dropna()
        .concat()
        .createIndexCheckpointTag()
        .map(lambda row: ops.dict_(x=row["truth"], y=row["guess"]))
        .unnest()[3]["x"]
    )
    run_name = x_val.run().name()
    assert weave.use(run_name) == "amber-glade-100"

    checkpoint_tag = x_val.indexCheckpoint()
    assert weave.use(checkpoint_tag) == 3

    assert weave.use(run_name) == "amber-glade-100"


def test_arrow_unnest_inner_tags(fake_wandb):
    fake_wandb.fake_api.add_mock(table_mock_filtered)
    run_name = (
        (
            ops.project("stacey", "mendeleev")
            .filteredRuns("{}", "-createdAt")
            .limit(50)
            .summary()
            .pick("table")
            .table()
            .rows()
        )
        .joinAll(lambda row: row["truth"], True)
        .map(lambda row: ops.dict_(x=row["truth"], y=row["guess"]))
        .unnest()[0]["x"]
        .run()
        .name()
    )
    assert weave.use(run_name) == "amber-glade-100"


def test_image_sha_from_table(fake_wandb):
    fake_wandb.fake_api.add_mock(table_mock2)
    img_node = (
        ops.project("stacey", "mendeleev")
        .runs()[0]
        .summary()["table"]
        .table()
        .rows()[0]["image"]
    )
    assert (
        weave.use(img_node.sha256)
        == "50a7232cb6785ffae981038af58de306192e5739a0b9d9903fa436f9f508e7d5"
    )


def test_image_in_summary(fake_wandb):
    fake_wandb.fake_api.add_mock(table_mock2)

    img_node = ops.project("stacey", "mendeleev").runs()[0].summary()["image"]

    assert (
        weave.use(img_node).sha256
        == "440fab0d6f537b4557a106fa7853453332650631ef580fd328c620bd8aa5a025"
    )


@pytest.mark.parametrize(
    "input_uri, expected_uri",
    [
        (
            "wandb-logged-artifact://long_server_id:latest/path",
            "wandb-artifact:///random-entity/random-project/run-2isjqtcr-Validation_table:303db33c9f9264768626/path",
        ),
        (
            "wandb-logged-artifact://long_server_id:v4/path",
            "wandb-artifact:///random-entity/random-project/run-2isjqtcr-Validation_table:303db33c9f9264768626/path",
        ),
        (
            "wandb-logged-artifact://1234567890/path",
            "wandb-artifact:///stacey/mendeleev/test_res_1fwmcd3q:303db33c9f9264768626/path",
        ),
        (
            "wandb-artifact:///input-entity/input-project/run-2isjqtcr-Validation_table/path",
            "wandb-artifact:///input-entity/input-project/run-2isjqtcr-Validation_table:303db33c9f9264768626/path",
        ),
    ],
)
def test_wb_artifact_uri_resolution(fake_wandb, input_uri, expected_uri):
    if input_uri == "wandb-logged-artifact://1234567890/path":
        fake_wandb.fake_api.add_mock(lambda q, index: artifact_version_sdk_response)
    else:
        fake_wandb.fake_api.add_mock(
            lambda q, index: {
                "artifactCollection": {
                    "id": "QXJ0aWZhY3RDb2xsZWN0aW9uOjUzNDYxMTc2",
                    "name": "run-2isjqtcr-Validation_table",
                    "state": "READY",
                    "project": {
                        "id": "UHJvamVjdDp2MTpNZXJnZWRfbGlndG5pbmc6Y29udGFjdC1lc3RpbWF0aW9u",
                        "name": "random-project",
                        "entity": {
                            "id": "RW50aXR5OjUwODA2Mg==",
                            "name": "random-entity",
                        },
                    },
                    "artifactMembership": {
                        "id": "QXJ0aWZhY3RDb2xsZWN0aW9uTWVtYmVyc2hpcDozNzAxNzE5NDE=",
                        "versionIndex": 4,
                        "commitHash": "303db33c9f9264768626",
                    },
                    "defaultArtifactType": {
                        "id": "QXJ0aWZhY3RUeXBlOjM1OTgxNA==",
                        "name": "run_table",
                    },
                }
            }
        )

    uri = uris.WeaveURI.parse(input_uri)
    ref = artifact_wandb.WandbArtifactRef.from_uri(uri=uri)
    assert str(ref) == expected_uri


def test_is_valid_version_string():
    assert not artifact_wandb.is_valid_version_index("latest")

    for v in ["v0", "v1", "v10", "v19"]:
        assert artifact_wandb.is_valid_version_index(v)

    for v in ["v0.0", "v1.0", "v10.0", "v19.0"]:
        assert not artifact_wandb.is_valid_version_index(v)

    for v in ["v01", "v0009"]:
        assert not artifact_wandb.is_valid_version_index(v)


def test_artifact_path_character_escaping():
    name = 12347187287418787843872388177814
    path = "table #3.table.json"
    result = wb_util.escape_artifact_path(
        f"wandb-client-artifact://{name}:latest/{path}"
    )
    uri = artifact_wandb.WeaveWBLoggedArtifactURI.parse(result)

    assert uri.path == path


def _do_test_gql_artifact_dir_path(node):
    dir_node = node.file("")
    dir_type_node = dir_node.pathReturnType("")
    dir_file_type_node = dir_node.pathReturnType("test_results.table.json")

    file_node = dir_node.path("test_results.table.json")
    file_type_node = file_node._get_op("type")()

    assert artifact_fs.FilesystemArtifactDirType().assign_type(weave.use(dir_type_node))
    assert artifact_fs.FilesystemArtifactFileType(
        weave.types.Const(weave.types.String(), "json"), wbObjectType=ops.TableType()
    ).assign_type(weave.use(dir_file_type_node))
    assert artifact_fs.FilesystemArtifactFileType(
        weave.types.Const(weave.types.String(), "json"), wbObjectType=ops.TableType()
    ).assign_type(weave.use(file_type_node))


def test_gql_artifact_dir_path(fake_wandb):
    fake_wandb.fake_api.add_mock(lambda q, ndx: artifact_browser_response)
    version_node = (
        ops.project("stacey", "mendeleev")
        .artifact("test_res_1fwmcd3q")
        .membershipForAlias("v0")
        .artifactVersion()
    )
    _do_test_gql_artifact_dir_path(version_node)


def test_filesystem_artifact_dir_path(fake_wandb):
    table = wandb.Table(data=[[1]], columns=["a"])
    art = wandb.Artifact("test_name", "test_type")
    art.add(table, "test_results")
    art_node = fake_wandb.mock_artifact_as_node(art)
    _do_test_gql_artifact_dir_path(art_node)


def test_filesystem_artifact_dir_dict(fake_wandb):
    table = wandb.Table(
        data=[[1, wandb.Image(np.zeros((32, 32)))]], columns=["a", "image"]
    )
    art = wandb.Artifact("test_name", "test_type")
    art.add(table, "test_results")
    art.add_reference("https://www.google.com", "google_link")
    art_node = fake_wandb.mock_artifact_as_node(art)
    assert weave.use(_as_w0_dict_(art_node.file(""))) == {
        "fullPath": "",
        "size": 954,
        "dirs": {
            "media": {
                "fullPath": "media/images/842c574e85966d3269f6.png",
                "size": 75,
                "dirs": {"images": 1},
                "files": {},
            }
        },
        "files": {
            "test_results.table.json": {
                "birthArtifactID": "TODO",
                "digest": "I/aUoc5M4r1UgTNwJUECMA==",
                "fullPath": "test_results.table.json",
                "size": 879,
                "type": "file",
                "url": "https://api.wandb.ai/artifacts/test_entity/23f694a1ce4ce2bd5481337025410230/test_results.table.json",
            },
            "google_link": {
                "birthArtifactID": "TODO",
                "digest": "https://www.google.com",
                "fullPath": "google_link",
                "size": 0,
                "type": "file",
                "ref": "https://www.google.com",
                "url": "https://www.google.com",
            },
        },
    }


def test_filesystem_artifact_by_id_dir_dict(fake_wandb):
    table = wandb.Table(
        data=[[1, wandb.Image(np.zeros((32, 32)))]], columns=["a", "image"]
    )
    art = wandb.Artifact("test_name", "test_type")
    art.add(table, "test_results")
    art.add_reference("https://www.google.com", "google_link")
    art_node = fake_wandb.mock_artifact_by_id_as_node(art)
    assert weave.use(_as_w0_dict_(art_node.file(""))) == {
        "fullPath": "",
        "size": 954,
        "dirs": {
            "media": {
                "fullPath": "media/images/842c574e85966d3269f6.png",
                "size": 75,
                "dirs": {"images": 1},
                "files": {},
            }
        },
        "files": {
            "test_results.table.json": {
                "birthArtifactID": "TODO",
                "digest": "I/aUoc5M4r1UgTNwJUECMA==",
                "fullPath": "test_results.table.json",
                "size": 879,
                "type": "file",
                "url": "https://api.wandb.ai/artifacts/_/23f694a1ce4ce2bd5481337025410230/test_results.table.json",
            },
            "google_link": {
                "birthArtifactID": "TODO",
                "digest": "https://www.google.com",
                "fullPath": "google_link",
                "size": 0,
                "type": "file",
                "ref": "https://www.google.com",
                "url": "https://www.google.com",
            },
        },
    }


def test_non_const_input_node(fake_wandb, cache_mode_minimal):
    fake_wandb.fake_api.add_mock(table_mock1)
    data_obj = weave.save({"project_name": "mendeleev"})
    cell_node = (
        # projectName arg is an OutputNode. Compile should execute
        # the branch to convert it to a ConstNode, so the gql compile
        # pass can see the value.
        ops.project("stacey", data_obj["project_name"])
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
