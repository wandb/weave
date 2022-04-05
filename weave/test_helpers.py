def assert_nodes_equal(n1, n2):
    # Don't override __eq__ on node! Nodes are mixed in with a class that
    #     contains weave methods for the given type, some of which need
    #     to override __eq__
    assert n1.to_json() == n2.to_json()
