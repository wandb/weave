import weave
from .. import ops as ops
import graphql
from . import fixture_fakewandb as fwb

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
    fake_wandb.add_mock(
        lambda query, ndx: {
            "project": {
                "id": 1,
                "name": "mendeleev",
                "entity": {
                    "id": 1,
                    "name": "stacey",
                },
                "runs_21303e3890a1b6580998e6aa8a345859": {
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
    log = fake_wandb.execute_log()
    assert len(log) == 1
    assert_gql_str_equal(
        log[0]["gql"],
        # Note: the inner project/entity query is because it is part of the required fragment for runs
        # this could in theory change in the future.
        """
        query WeavePythonCG { 
            project(name: "mendeleev", entityName: "stacey") {
                id
                name
                entity {
                    id 
                    name
                } 
                runs_21303e3890a1b6580998e6aa8a345859: runs(first: 50) {
                    edges {
                        node {
                            id
                            name
                            project {
                                id
                                name
                                entity {
                                    id
                                    name
                                }
                            }
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
    fake_wandb.add_mock(
        lambda query, ndx: {
            "project": {
                **fwb.project_payload,
                "runs_6e908597bd3152c2f0457f6283da76b9": {
                    "edges": [
                        {
                            "node": {
                                **fwb.run_payload,
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

    assert weave.use(summary) == [0.1, 0.1]
    log = fake_wandb.execute_log()
    assert len(log) == 1
    assert_gql_str_equal(
        log[0]["gql"],
        # Note: the inner project/entity query is because it is part of the required fragment for runs
        # this could in theory change in the future.
        """query WeavePythonCG {
            project(name: "mendeleev", entityName: "stacey") {
                id
                name
                entity {
                id
                name
                }
                runs_6e908597bd3152c2f0457f6283da76b9: runs(
                first: 50
                filters: "{}"
                order: "-createdAt"
                ) {
                edges {
                    node {
                    id
                    name
                    project {
                        id
                        name
                        entity {
                        id
                        name
                        }
                    }
                    summaryMetrics
                    }
                }
                }
            }
            }""",
    )
