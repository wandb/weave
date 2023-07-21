from .. import gql_to_weave
from .. import weave_types as types


def test_simple_query():
    query = """
    query {
        project(name: "test") {
            id
            name
        }
    }
    """
    return_type = gql_to_weave.get_query_weave_type(query)
    assert return_type == types.TypedDict(
        {
            "project": types.TypedDict(
                {
                    "id": types.String(),
                    "name": types.String(),
                }
            )
        }
    )


def test_artifact_query():
    query = """
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
        """
    return_type = gql_to_weave.get_query_weave_type(query)
    assert return_type == types.TypedDict(
        {
            "project_8d1592567720841659de23c02c97d594": types.TypedDict(
                {
                    "id": types.String(),
                    "name": types.String(),
                    "runs_261949318143369aa6c158af92afee03": types.TypedDict(
                        {
                            "edges": types.List(
                                types.TypedDict(
                                    {
                                        "node": types.TypedDict(
                                            {
                                                "id": types.String(),
                                                "name": types.String(),
                                                "summaryMetricsSubset": types.optional(
                                                    types.String()
                                                ),
                                                "project": types.TypedDict(
                                                    {
                                                        "id": types.String(),
                                                        "name": types.String(),
                                                        "entity": types.TypedDict(
                                                            {
                                                                "id": types.String(),
                                                                "name": types.String(),
                                                            }
                                                        ),
                                                    }
                                                ),
                                            }
                                        )
                                    }
                                )
                            )
                        }
                    ),
                }
            )
        }
    )
