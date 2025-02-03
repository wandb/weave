import re


class RegexMatcher:
    def __init__(self, regex):
        self.regex = regex

    def __eq__(self, other):
        assert isinstance(other, str)
        return bool(re.match(self.regex, other))

    def __repr__(self):
        return "<RegexMatcher '%s'>" % self.regex


def assert_nodes_equal(n1, n2):
    # Don't override __eq__ on node! Nodes are mixed in with a class that
    #     contains weave methods for the given type, some of which need
    #     to override __eq__
    assert n1.to_json() == n2.to_json()
