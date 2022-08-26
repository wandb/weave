from ..decorators import op

# TODO: generic
@op()
def union(s1: list[str], s2: list[str]) -> list[str]:
    return list(set(s1).union(set(s2)))
