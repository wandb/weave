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
