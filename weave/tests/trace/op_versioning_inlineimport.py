import weave


@weave.op()
def versioned_op_inline_import(a: int) -> float:
    import numpy

    return numpy.array([a, a]).mean()


@weave.op()
def versioned_op_inline_import_alias(a: int) -> float:
    import numpy as np

    return np.array([a, a]).mean()


@weave.op()
def versioned_op_inline_importfrom(a: int) -> float:
    from numpy import array

    return array([a, a]).mean()
