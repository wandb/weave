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


def test_multi_root_query():
    query = """
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
                projects_500:projects(limit:500){
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
        """

    return_type = gql_to_weave.get_query_weave_type(query)
    assert return_type == types.TypedDict(
        {
            "project_8d1592567720841659de23c02c97d594": types.TypedDict(
                {
                    "id": types.String(),
                    "name": types.String(),
                    "createdAt": types.Timestamp(),
                }
            ),
            "project_3c237e5b25fed9a705b21513dd7921c6": types.TypedDict(
                {
                    "id": types.String(),
                    "name": types.String(),
                    "runs_c1233b7003317090ab5e2a75db4ad965": types.TypedDict(
                        {
                            "edges": types.List(
                                types.TypedDict(
                                    {
                                        "node": types.TypedDict(
                                            {
                                                "id": types.String(),
                                                "name": types.String(),
                                            }
                                        )
                                    }
                                )
                            )
                        }
                    ),
                }
            ),
            "instance": types.TypedDict(
                {
                    "projects_500": types.TypedDict(
                        {
                            "edges": types.List(
                                types.TypedDict(
                                    {
                                        "node": types.TypedDict(
                                            {
                                                "id": types.String(),
                                                "name": types.String(),
                                                "createdAt": types.Timestamp(),
                                            }
                                        )
                                    }
                                )
                            )
                        }
                    )
                }
            ),
        }
    )


def test_inline_fragments():
    query = """query WeavePythonCG {
  project_518fa79465d8ffaeb91015dce87e092f: project(
    name: "mendeleev"
    entityName: "stacey"
  ) {
    id
    name
    artifactType_46d22fef09db004187bb8da4b5e98c58: artifactType(
      name: "test_results"
    ) {
      id
      name
      artifactCollections_c1233b7003317090ab5e2a75db4ad965: artifactCollections(
        first: 100
      ) {
        edges {
          node {
            id
            name

            artifacts_c1233b7003317090ab5e2a75db4ad965: artifacts(first: 100) {
              edges {
                node {
                  id
                  createdBy {
                    __typename
                    ... on Run {
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
      }
    }
  }
}
    """

    return_type = gql_to_weave.get_query_weave_type(query)
    expected = types.TypedDict(
        {
            "project_518fa79465d8ffaeb91015dce87e092f": types.TypedDict(
                {
                    "id": types.String(),
                    "name": types.String(),
                    "artifactType_46d22fef09db004187bb8da4b5e98c58": types.TypedDict(
                        {
                            "id": types.String(),
                            "name": types.String(),
                            "artifactCollections_c1233b7003317090ab5e2a75db4ad965": types.TypedDict(
                                {
                                    "edges": types.List(
                                        types.TypedDict(
                                            {
                                                "node": types.TypedDict(
                                                    {
                                                        "id": types.String(),
                                                        "name": types.String(),
                                                        "artifacts_c1233b7003317090ab5e2a75db4ad965": types.TypedDict(
                                                            {
                                                                "edges": types.List(
                                                                    types.TypedDict(
                                                                        {
                                                                            "node": types.TypedDict(
                                                                                {
                                                                                    "id": types.String(),
                                                                                    "createdBy": types.UnionType(
                                                                                        types.TypedDict(
                                                                                            {
                                                                                                "__typename": types.Const(
                                                                                                    types.String(),
                                                                                                    "Run",
                                                                                                ),
                                                                                                "id": types.String(),
                                                                                                "name": types.String(),
                                                                                                "displayName": types.optional(
                                                                                                    types.String()
                                                                                                ),
                                                                                            }
                                                                                        ),
                                                                                        types.TypedDict(
                                                                                            {
                                                                                                "__typename": types.Const(
                                                                                                    types.String(),
                                                                                                    "User",
                                                                                                ),
                                                                                            }
                                                                                        ),
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
                                    )
                                }
                            ),
                        }
                    ),
                }
            )
        }
    )

    assert return_type == expected
