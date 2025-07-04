import gql

VIEWER_QUERY = gql.gql(
    """
    query Viewer {
        viewer {
            username
        }
    }
    """
)
