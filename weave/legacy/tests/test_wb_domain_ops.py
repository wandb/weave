import json

import graphql
import wandb

import weave
from weave.legacy.weave import ops
from weave.legacy.weave.language_features.tagging import tagged_value_type
from weave.legacy.weave.ops_domain import wb_domain_types
from weave.legacy.weave.ops_primitives import _dict_utils

from ...legacy.weave import registry_mem
from ...tests import fixture_fakewandb as fwb

"""
Tests in this file whould be used to test the graphs that can be constructed
with the ops in `ops_domain`. This file compliments `test_wb.py`. `test_wb.py`
is inteded to test common WB app graphs that come from high traffic page (eg.
workspaces, artifact browser, etc.) and primarily tests for correctness of the
result. This file is intended to help author unit tests for all the different
ops as well as test for the correctness of the GQL query that is generated as a
result of executing such graph. One example is probivided below
`test_root_project_runs`, but many more should be added.
"""


def assert_gql_str_equal(gql_doc, exp_str):
    stripped_exp = graphql.language.print_ast(graphql.language.parse(exp_str))
    stripped_got = graphql.language.print_ast(
        graphql.language.parse(gql_doc.loc.source.body)
    )
    assert stripped_got == stripped_exp


def test_root_project_runs(fake_wandb):
    runs_node = ops.project("stacey", "mendeleev").runs()
    runs_0_id = runs_node[0].id()
    runs_1_iid = runs_node[1].internalId()
    runs_2_name = runs_node[2].name()
    concat_node = runs_0_id.add(runs_1_iid).add(runs_2_name)
    fake_wandb.fake_api.add_mock(
        lambda query, ndx: {
            "project_518fa79465d8ffaeb91015dce87e092f": {
                "id": 1,
                "name": "mendeleev",
                "entity": {
                    "id": 1,
                    "name": "stacey",
                },
                "runs_c1233b7003317090ab5e2a75db4ad965": {
                    "edges": [
                        {
                            "node": {
                                "id": "id_0",
                                "name": "2ed5xwpn",
                                "displayName": "crazy-cat-5",
                            }
                        },
                        {
                            "node": {
                                "id": "id_1",
                                "name": "1x36vcvi",
                                "displayName": "large-cat-6",
                            }
                        },
                        {
                            "node": {
                                "id": "id_2",
                                "name": "f54e6rg7",
                                "displayName": "small-cat-7",
                            }
                        },
                    ]
                },
            }
        }
    )
    assert weave.use(concat_node) == "2ed5xwpnid_1small-cat-7"
    log = fake_wandb.fake_api.execute_log()
    assert len(log) == 1
    assert_gql_str_equal(
        log[0]["gql"],
        # Note: the inner project/entity query is because it is part of the required fragment for runs
        # this could in theory change in the future.
        """
        query WeavePythonCG {
            project_518fa79465d8ffaeb91015dce87e092f: project(name: "mendeleev", entityName: "stacey") {
                id
                name
                runs_c1233b7003317090ab5e2a75db4ad965: runs(first: 100) {
                    edges {
                        node {
                            id
                            name
                            displayName
                        }
                    }
                }
            }
        }""",
    )


def test_root_project_concat(fake_wandb):
    runs_node_1 = ops.project("stacey", "mendeleev").filteredRuns("{}", "-createdAt")
    runs_node_2 = ops.project("stacey", "mendeleev").filteredRuns("{}", "-createdAt")
    fake_wandb.fake_api.add_mock(
        lambda query, ndx: {
            "project_518fa79465d8ffaeb91015dce87e092f": {
                **fwb.project_payload,
                "runs_261949318143369aa6c158af92afee03": {
                    "edges": [
                        {
                            "node": {
                                **fwb.run_payload,
                                "summaryMetricsSubset": '{"loss": 0.1}',
                                "summaryMetrics": '{"loss": 0.1}',
                            },
                        }
                    ]
                },
            }
        }
    )
    summary = (
        ops.make_list(a=runs_node_1, b=runs_node_2).concat().limit(50).summary()["loss"]
    )
    log = fake_wandb.fake_api.execute_log()
    assert len(log) == 1
    # The first request is to refineSummary, so we request summaryMetrics
    assert_gql_str_equal(
        log[0]["gql"],
        # Note: the inner project/entity query is because it is part of the required fragment for runs
        # this could in theory change in the future.
        """query WeavePythonCG {
            project_518fa79465d8ffaeb91015dce87e092f: project(name: "mendeleev", entityName: "stacey") {
                id
                name
                runs_261949318143369aa6c158af92afee03: runs(
                first: 100
                filters: "{}"
                order: "-createdAt"
                ) {
                edges {
                    node {
                    id
                    name
                    summaryMetrics
                    }
                }
                }
            }
            }""",
    )
    assert tagged_value_type.TaggedValueType(
        weave.types.TypedDict(property_types={"project": wb_domain_types.ProjectType}),
        weave.types.List(
            object_type=tagged_value_type.TaggedValueType(
                weave.types.TypedDict(
                    property_types={
                        "run": tagged_value_type.TaggedValueType(
                            weave.types.TypedDict(
                                property_types={"project": wb_domain_types.ProjectType}
                            ),
                            wb_domain_types.RunType,
                        )
                    }
                ),
                weave.types.Float(),
            )
        ),
    ).assign_type(summary.type)

    assert weave.use(summary) == [0.1, 0.1]
    # The second request is the graph we constructed above. Projection
    # pushdown should occur (we should request summaryMetrics with the keys
    # arg)
    assert len(log) == 2
    assert_gql_str_equal(
        log[1]["gql"],
        # Note: the inner project/entity query is because it is part of the required fragment for runs
        # this could in theory change in the future.
        """query WeavePythonCG {
            project_518fa79465d8ffaeb91015dce87e092f: project(name: "mendeleev", entityName: "stacey") {
                id
                name
                runs_261949318143369aa6c158af92afee03: runs(
                first: 100
                filters: "{}"
                order: "-createdAt"
                ) {
                edges {
                    node {
                    id
                    name
                    summaryMetricsSubset: summaryMetrics(keys: ["loss"])
                    project {
                        id
                        name
                        entity {
                        id
                        name
                        }
                    }
                    }
                }
                }
            }
            }""",
    )


def test_all_projects(fake_wandb):
    all_projects = ops.project_ops.root_all_projects().runs().flatten().name()
    fake_wandb.fake_api.add_mock(
        lambda query, ndx: {
            "instance": {
                "projects_500": {
                    "edges": [
                        {
                            "node": {
                                **fwb.project_payload,
                                "runs_c1233b7003317090ab5e2a75db4ad965": {
                                    "edges": [
                                        {
                                            "node": {
                                                **fwb.run_payload,
                                                "displayName": "crazy-cat-5",
                                            },
                                        }
                                    ]
                                },
                            }
                        }
                    ]
                }
            }
        }
    )
    assert weave.use(all_projects) == ["crazy-cat-5"]
    log = fake_wandb.fake_api.execute_log()
    assert len(log) == 1
    assert_gql_str_equal(
        log[0]["gql"],
        # Note: the inner project/entity query is because it is part of the required fragment for runs
        # this could in theory change in the future.
        """query WeavePythonCG {
            instance {
                projects_500: projects {
                    edges {
                        node {
                            id
                            name
                            runs_c1233b7003317090ab5e2a75db4ad965: runs(first: 100) {
                                edges {
                                    node {
                                        id
                                        name
                                        displayName
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }""",
    )


def test_rpt_op(fake_wandb):
    rpt_op = registry_mem.memory_registry.get_op("rpt_weekly_users_by_country_by_repo")
    data = rpt_op("stacey")["rows"]["user_fraction"]
    fake_wandb.fake_api.add_mock(
        lambda query, ndx: {
            "repoInsightsPlotData_541e3882f7cccacef0f697358bac12e3": {
                "edges": [
                    {"node": {"row": [0.5, "US", 1674068711.643377, "pytorch"]}},
                    {"node": {"row": [0.75, "CA", 1674068711.643377, "pytorch"]}},
                ],
                "schema": [
                    {"Name": "user_fraction", "Type": "FLOAT"},
                    {"Name": "country", "Type": "STRING"},
                    {"Name": "created_week", "Type": "TIMESTAMP"},
                    {"Name": "framework", "Type": "STRING"},
                ],
                "isNormalizedUserCount": True,
            }  #
        }
    )
    assert weave.use(data) == [0.5, 0.75]
    log = fake_wandb.fake_api.execute_log()
    assert len(log) == 1
    assert_gql_str_equal(
        log[0]["gql"],
        # Note: the inner project/entity query is because it is part of the required fragment for runs
        # this could in theory change in the future.
        """query WeavePythonCG {
            repoInsightsPlotData_541e3882f7cccacef0f697358bac12e3: repoInsightsPlotData(
                plotName: "weekly_users_by_country_by_repo"
                repoName: "stacey"
                first: 100000
            ) {
                edges {
                    node {
                        row
                    }
                }
                schema
                isNormalizedUserCount
            }
        }""",
    )


def test_multi_root_merging(fake_wandb, cache_mode_minimal):
    fake_wandb.fake_api.add_mock(
        lambda query, ndx: {
            "project_8d1592567720841659de23c02c97d594": {
                **fwb.project_payload,
                "name": "p_0",
                "createdAt": "2020-01-01T00:00:00.000+00:00",
            },
            "project_3c237e5b25fed9a705b21513dd7921c6": {
                **fwb.project_payload,
                "name": "p_1",
                "runs_c1233b7003317090ab5e2a75db4ad965": {
                    "edges": [
                        {
                            "node": {
                                **fwb.run_payload,
                            }
                        }
                    ]
                },
            },
            "instance": {
                "projects_500": {
                    "edges": [
                        {
                            "node": {
                                **fwb.project_payload,
                                "name": "p_0",
                                "createdAt": "2021-01-01T00:00:00.000+00:00",
                            }
                        },
                        {
                            "node": {
                                **fwb.project_payload,
                                "name": "p_1",
                                "createdAt": "2022-01-01T00:00:00.000+00:00",
                            }
                        },
                    ]
                }
            },
        }
    )
    p_0_a = ops.project("e_0", "p_0")
    p_0_b = ops.project("e_0", "p_0")
    p_1_a = ops.project("e_1", "p_1")

    p_0_name = p_0_a.name()
    p_0_ca = p_0_b.createdAt().toNumber()
    p_1_a_runs = p_1_a.runs().count()

    r_p_a = ops.project_ops.root_all_projects()
    r_p_b = ops.project_ops.root_all_projects()
    r_p_a_name = r_p_a.name()
    r_p_b_ca = r_p_b.createdAt().toNumber()

    assert weave.use([p_0_name, p_0_ca, p_1_a_runs, r_p_a_name, r_p_b_ca]) == [
        "p_0",
        1577836800000,
        1,
        ["p_0", "p_1"],
        [1609459200000, 1640995200000],
    ]

    log = fake_wandb.fake_api.execute_log()
    assert len(log) == 1
    assert_gql_str_equal(
        log[0]["gql"],
        """
        query WeavePythonCG{
            project_8d1592567720841659de23c02c97d594:project(name:"p_0" entityName:"e_0"){
                id
                name
                createdAt
            }
            project_3c237e5b25fed9a705b21513dd7921c6:project(name:"p_1" entityName:"e_1"){
                id
                name
                runs_c1233b7003317090ab5e2a75db4ad965:runs(first:100){
                    edges{
                        node{
                            id
                            name
                        }
                    }
                }
            }
            instance{
                projects_500:projects {
                    edges{
                        node{
                            id
                            name
                            createdAt
                        }
                    }
                }
            }
        }
        """,
    )


def test_two_level_summary(fake_wandb):
    def _mocked_query(query, ndx):
        run_selections = (
            query["gql"]
            .definitions[0]
            .selection_set.selections[0]
            .selection_set.selections[2]
            .selection_set.selections[0]
            .selection_set.selections[0]
            .selection_set.selections
        )
        assert (
            len(
                list(
                    f
                    for f in run_selections
                    if f.name.value == "summaryMetrics"
                    and f.alias
                    and f.alias.value == "summaryMetricsSubset"
                )
            )
            == 1
        )
        return {
            "project_8d1592567720841659de23c02c97d594": {
                **fwb.project_payload,
                "name": "p_1",
                "runs_c1233b7003317090ab5e2a75db4ad965": {
                    "edges": [
                        {
                            "node": {
                                "name": "r_1",
                                "project": {"name": "p_1", "entity": {"name": "e_1"}},
                                "summaryMetricsSubset": json.dumps({"a": 1, "b": "x"}),
                            }
                        },
                        {
                            "node": {
                                "name": "r_1",
                                "project": {"name": "p_1", "entity": {"name": "e_1"}},
                                "summaryMetricsSubset": json.dumps({"a": 2, "b": "y"}),
                            }
                        },
                    ]
                },
            }
        }

    fake_wandb.fake_api.add_mock(_mocked_query)
    n = (
        ops.project("e_0", "p_0")
        .runs()
        .filter(lambda r: r.summary()["a"] == 1)
        .summary()["b"]
    )
    assert weave.use(n) == ["x"]


def test_escaped_gql_query(fake_wandb):
    response = {
        "project_8d1592567720841659de23c02c97d594": {
            "id": "UHJvamVjdDp2MTpzYWdlbWFrZXItcGVvcGxlLXZlaGljbGUtY2xhc3Mtc3BsaXR0aW5nOmFjdHVhdGVhaQ==",
            "name": "",
            "entity": {"id": "RW50aXR5OjE0NzUxNw==", "name": "e_0"},
            "runs_261949318143369aa6c158af92afee03": {"edges": []},
        }
    }

    fake_wandb.fake_api.add_mock(lambda q, ix: response)

    key = "Tables/NMS_0\\.45_IOU_0\\.5"
    node = (
        ops.project("e_0", "p_0")
        .filteredRuns("{}", "-createdAt")
        .limit(1)
        .summary()[key]
        .table()
        .rows()
        .dropna()
        .concat()
        .createIndexCheckpointTag()
        .index(6)["label"]
    )

    log = fake_wandb.fake_api.execute_log()
    assert_gql_str_equal(
        log[1]["gql"],
        # Note: the inner project/entity query is because it is part of the required fragment for runs
        # this could in theory change in the future.
        """
        query WeavePythonCG {
        project_8d1592567720841659de23c02c97d594: project(
            name: "p_0"
            entityName: "e_0"
        ) {
            id
            name
            runs_261949318143369aa6c158af92afee03: runs(
            first: 100
            filters: "{}"
            order: "-createdAt"
            ) {
            edges {
                node {
                id
                name
                summaryMetricsSubset: summaryMetrics(
                    keys: ["Tables/NMS_0.45_IOU_0.5"]
                )
                project {
                    id
                    name
                    entity {
                    id
                    name
                    }
                }
                }
            }
            }
        }
        }
        """,
    )


def test_null_propagation_through_nonnull_gql_ops(fake_wandb):
    fake_wandb.fake_api.add_mock(
        lambda q, ix: {"project_8d1592567720841659de23c02c97d594": None}
    )

    # this should fail?
    node = ops.project("e_0", "p_0").run("r_0").name()
    assert weave.use(node) == None
