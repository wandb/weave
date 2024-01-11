import weave
from numpy import array


@weave.op()
def versioned_op_importfrom(a: int) -> float:
    return array([x + 1 for x in range(a)]).mean()
