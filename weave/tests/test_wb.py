import pytest

from .. import api as weave
from .. import ops as ops
from . import weavejs_ops as wjs

from . import weavejs_ops
import json
from . import fixture_fakewandb as fwb
from .. import graph
from ..ops_domain import wb_domain_types as wdt
from ..ops_domain import artifact_membership_ops as amo
from ..ops_primitives import list_, dict_
from .. import weave_types as types

from .. import ops_arrow as arrow
from ..ops_domain.wbmedia import TableClientArtifactFileRef
import cProfile
from ..language_features.tagging.tagged_value_type import TaggedValueType

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
                    },
                },
                {
                    "node": {
                        **fwb.run2_payload,  # type: ignore
                        "summaryMetrics": json.dumps({}),
                        "displayName": "run2-display_name",
                    },
                },
                {
                    "node": {
                        **fwb.run3_payload,  # type: ignore
                        "summaryMetrics": json.dumps(
                            {
                                "table": {
                                    "_type": "table-file",
                                    "artifact_path": "wandb-client-artifact://1122334455/test_results.table.json",
                                },
                            }
                        ),
                        "displayName": "run3-display_name",
                    },
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

project_run_artifact_response = {
    "project": {
        **fwb.project_payload,  # type: ignore
        "runs_21303e3890a1b6580998e6aa8a345859": {
            "edges": [
                {
                    "node": {
                        **fwb.run_payload,  # type: ignore
                        "outputArtifacts_21303e3890a1b6580998e6aa8a345859": {
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
        "_wandb_artifacts/artifacts/test_res_1fwmcd3q_v0_1234567890/media/images/8f65e54dc684f7675aec.png"
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


def table_mock1(q, ndx):
    if ndx == 0:
        return workspace_response
    elif ndx == 1:
        return artifact_version_sdk_response
    elif ndx == 2:
        return workspace_response
    elif ndx == 3:
        return artifact_version_sdk_response
    pass


def table_mock2(q, ndx):
    if ndx == 0:
        return workspace_response
    elif ndx == 1:
        return artifact_version_sdk_response
    elif ndx == 2:
        return artifact_version_sdk_response


def test_map_gql_op(fake_wandb):
    fake_wandb.add_mock(lambda q, ndx: project_run_artifact_response)
    node = (
        ops.project("stacey", "mendeleev")
        .runs()
        .limit(1)
        .loggedArtifactVersions()
        .limit(1)[0][0]
        .name()
    )
    assert weave.use(node) == "test_res_1fwmcd3q:v0"


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
    fake_wandb.add_mock(table_mock1)
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
    fake_wandb.add_mock(table_mock1)
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
    fake_wandb.add_mock(table_mock2)
    cell_node = ops.project("stacey", "mendeleev").runs().summary()["table"].table()
    assert cell_node.type == TaggedValueType(
        types.TypedDict(property_types={"project": wdt.ProjectType}),
        types.List(
            object_type=types.optional(
                TaggedValueType(
                    types.TypedDict(property_types={"run": wdt.RunType}),
                    ops.TableType(),
                )
            )
        ),
    )


def test_workspace_table_rows_type(fake_wandb):
    fake_wandb.add_mock(table_mock2)
    cell_node = (
        ops.project("stacey", "mendeleev").runs().summary()["table"].table().rows()
    )
    assert cell_node.type == TaggedValueType(
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
                                "score_Animalia": types.optional(types.Float()),
                                "score_Amphibia": types.optional(types.Float()),
                                "score_Arachnida": types.optional(types.Float()),
                                "score_Aves": types.optional(types.Float()),
                                "score_Fungi": types.optional(types.Float()),
                                "score_Insecta": types.optional(types.Float()),
                                "score_Mammalia": types.optional(types.Float()),
                                "score_Mollusca": types.optional(types.Float()),
                                "score_Plantae": types.optional(types.Float()),
                                "score_Reptilia": types.optional(types.Float()),
                            }
                        )
                    ),
                )
            )
        ),
    )


def test_table_tags_column_first(fake_wandb):
    fake_wandb.add_mock(table_mock1)
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
    fake_wandb.add_mock(table_mock2)
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
        "run_names": [
            {"name": "amber-glade-100"},
            {"name": "run2-display_name"},
            {"name": "run3-display_name"},
        ],
    }


def test_lambda_gql_stitch(fake_wandb):
    fake_wandb.add_mock(lambda q, ndx: {"project": fwb.project_payload})
    weave.use(
        ops.make_list(a="a", b="b", c="c").map(
            lambda x: x + ops.project("stacey", "mendeleev").name()
        )
    ) == None


def test_arrow_groupby_nested_tag_stripping(fake_wandb):
    fake_wandb.add_mock(lambda q, ndx: file_path_response)
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


def test_arrow_tag_stripping(fake_wandb):
    fake_wandb.add_mock(lambda q, ndx: file_path_response)
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
    fake_wandb.add_mock(
        lambda q, ndx: {
            "project": {
                **fwb.project_payload,  # type: ignore
                "artifactCollection_d651817074b6a8074e87e9dfd5767726": {
                    **fwb.artifactSequence_payload,  # type: ignore
                },
            }
        }
    )
    ac_node = ops.project("stacey", "mendeleev").artifact("test_res_1fwmcd3q")
    assert weave.use(ac_node) != None


def test_loading_artifact_browser_request_2(fake_wandb):
    ac_node = ops.project("stacey", "mendeleev").artifact("test_res_1fwmcd3q")
    # Leaf 2: Get collection details
    fake_wandb.add_mock(
        lambda q, ndx: {
            "project": {
                **fwb.project_payload,  # type: ignore
                "artifactCollection_d651817074b6a8074e87e9dfd5767726": {
                    **fwb.artifactSequence_payload,  # type: ignore
                    "__typename": "ArtifactSequence",
                    "project": fwb.project_payload,
                    "artifacts_21303e3890a1b6580998e6aa8a345859": {
                        "edges": [{"node": {**fwb.artifactVersion_payload}}]
                    },
                    "artifactMembership_fe9cc269bee939ccb54ebba88c6087dd": {
                        **fwb.artifactMembership_payload
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
                    "artifactMemberships_21303e3890a1b6580998e6aa8a345859": {
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
    fake_wandb.clear_mock_handlers()
    fake_wandb.add_mock(
        lambda q, ndx: {
            "project": {
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
    fake_wandb.clear_mock_handlers()
    fake_wandb.add_mock(
        lambda q, ndx: {
            "project": {
                **fwb.project_payload,  # type: ignore
                "artifactCollection_d651817074b6a8074e87e9dfd5767726": {
                    **fwb.artifactSequence_payload,  # type: ignore
                    "artifactMembership_a9aa34b91abdb163475121bd51290fcb": {
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


def test_loading_artifact_browser_request_3(fake_wandb):
    ac_node = ops.project("stacey", "mendeleev").artifact("test_res_1fwmcd3q")
    mem_node = ac_node.membershipForAlias("v0")
    # Leaf 5: Get the specific artifact version details
    fake_wandb.add_mock(
        lambda q, ndx: {
            "project": {
                **fwb.project_payload,  # type: ignore
                "artifactCollection_d651817074b6a8074e87e9dfd5767726": {
                    **fwb.artifactSequence_payload,  # type: ignore
                    "artifactMembership_78e7a3fd51159b4fdfb0815be0b0f92c": {
                        **fwb.artifactMembership_payload,  # type: ignore
                        "artifact": {
                            **fwb.artifactVersion_payload,  # type: ignore
                            "description": "",
                            "digest": "fd2948ad1c05b8d0084609a726a5da68",
                            "createdAt": "2021-07-10T19:27:32",
                            "usedBy_21303e3890a1b6580998e6aa8a345859": {
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
                                "inputArtifacts_21303e3890a1b6580998e6aa8a345859": {
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
                            "aliases_21303e3890a1b6580998e6aa8a345859": {
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
                                    "artifactCollections_9dd867443b22f4b22c2b85e7719e3d46": {
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
                            "artifactMemberships_21303e3890a1b6580998e6aa8a345859": {
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
    fake_wandb.clear_mock_handlers()
    fake_wandb.add_mock(
        lambda q, ndx: {
            "project": {
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
    fake_wandb.clear_mock_handlers()
    fake_wandb.add_mock(
        lambda q, ndx: {
            "project": {
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
        "system/gpu.0.powerWatts": {
            "typeCounts": [{"type": "number", "count": 51}],
            "monotonic": False,
            "previousValue": -1,
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


def run_history_mocker(q, ndx):
    if ndx == 0:
        return {
            "project": {
                **fwb.project_payload,  # type: ignore
                "runs_21303e3890a1b6580998e6aa8a345859": {
                    "edges": [
                        {
                            "node": {
                                **fwb.run_payload,  # type: ignore
                                "first_10_history_rows": example_history,
                                "historyKeys": example_history_keys,
                            }
                        }
                    ]
                },
            }
        }
    elif ndx == 1:
        return {
            "project": {
                **fwb.project_payload,  # type: ignore
                "runs_21303e3890a1b6580998e6aa8a345859": {
                    "edges": [
                        {
                            "node": {
                                **fwb.run_payload,  # type: ignore
                                "first_10_history_rows": example_history,
                                "historyKeys": example_history_keys,
                                "history": example_history,
                            }
                        }
                    ]
                },
            }
        }


def test_run_history(fake_wandb):
    fake_wandb.add_mock(run_history_mocker)
    node = ops.project("stacey", "mendeleev").runs()[0].history()
    assert isinstance(node.type, TaggedValueType)
    assert types.List(
        types.TypedDict(
            {
                "system/gpu.0.powerWatts": types.Number(),
                "epoch": types.Number(),
                "predictions_10K": types.union(
                    types.NoneType(), TableClientArtifactFileRef.WeaveType()
                ),
            }
        )
    ).assign_type(node.type.value)
    assert len(weave.use(node)) == len(example_history)


def run_history_as_of_mocker(q, ndx):
    if ndx == 0:
        return {
            "project": {
                **fwb.project_payload,  # type: ignore
                "runs_21303e3890a1b6580998e6aa8a345859": {
                    "edges": [
                        {
                            "node": {
                                **fwb.run_payload,  # type: ignore
                                "history_d3d9446802a44259755d38e6d163e820": example_history[
                                    9
                                ],
                            }
                        }
                    ]
                },
            }
        }


def test_run_history_as_of(fake_wandb):
    fake_wandb.add_mock(run_history_as_of_mocker)
    node = ops.project("stacey", "mendeleev").runs()[0].historyAsOf(10)
    assert isinstance(node.type, TaggedValueType)
    assert types.TypedDict(
        {
            "_step": types.Number(),
            "_timestamp": types.Number(),
            "_runtime": types.Number(),
            "predictions_10K": TableClientArtifactFileRef.WeaveType(),
        }
    ).assign_type(node.type.value)
    assert weave.use(node).keys() == json.loads(example_history[9]).keys()


def test_artifact_membership_link(fake_wandb):
    fake_wandb.add_mock(lambda q, ndx: artifact_browser_response)
    node = amo.artifact_membership_link(
        ops.project("stacey", "mendeleev")
        .artifact("test_res_1fwmcd3q")
        .membershipForAlias("v0")
    )

    assert weave.use(node) == wdt.Link(
        name="test_res_1fwmcd3q:v0",
        url="/stacey/mendeleev/artifacts/test_results/test_res_1fwmcd3q/v0",
    )

def test_artifact_browser_js(fake_wandb):
    fake_wandb.add_mock(lambda q, ndx: artifact_browser_response)
    node = wjs.root_project("stacey", "mendeleev")
    node = wjs.project_artifact(node, "test_res_1fwmcd3q")
    node = wjs.artifact_membership_for_alias(node, "v0")
    node = wjs.artifact_membership_artifact_version(node)
    node = wjs.artifact_version_file(node, "test_results.table.json")
    node = wjs.file_table(node)
    node = wjs.table_rows(node)
    node = wjs.create_index_checkpoint(node)
    all_nodes = []
    for ndx in [0, 1, 2, 3]:
        for key in ["guess", "score_Amphibia", "score_Animalia"]:
            all_nodes.append(wjs.weavejs_pick(wjs.index(node, ndx), key))
    assert weave.use(all_nodes) == ['Fungi', 0.0034, 0.0025, 'Fungi', 0.008, 0.0016, 'Fungi', 0.0, 0.0001, 'Fungi', 0.0047, 0.0008]