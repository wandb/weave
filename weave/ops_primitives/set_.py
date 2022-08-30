from ..decorators import op

# TODO: generic
@op()
def union(s1: list[str], s2: list[str]) -> list[str]:
    return list(set(s1).union(set(s2)))


@op()
def subtract(s1: list[str], s2: list[str]) -> list[str]:
    return list(set(s1).difference(set(s2)))
