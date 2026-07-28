import weave


@weave.op
def versioned_op_inline_import(a: int) -> float:
    import numpy  # noqa: PLC0415

    return numpy.array([a, a]).mean()


@weave.op
def versioned_op_inline_import_alias(a: int) -> float:
    import numpy as np  # noqa: PLC0415

    return np.array([a, a]).mean()


@weave.op
def versioned_op_inline_importfrom(a: int) -> float:
    from numpy import array  # noqa: PLC0415

    return array([a, a]).mean()
