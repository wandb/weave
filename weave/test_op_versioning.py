from . import api as weave


def test_op_versioning():
    @weave.op()
    def versioned_op(a: int, b: int) -> int:
        return a + b

    assert weave.use(versioned_op(1, 2)) == 3

    @weave.op()
    def versioned_op(a: int, b: int) -> int:
        return a - b

    # Because it is a new version with different code, this
    # should not hit memoized cache.
    assert weave.use(versioned_op(1, 2)) == -1

    # TODO: make it so you don't have to access op_def
    # TODO: version ordering is wrong!
    v0_ref = weave.versions(versioned_op.op_def)[1]
    # TODO: probably nicer if I don't have to call .get() here?
    v0 = v0_ref.get()
    # TODO: make OpDef callable
    assert weave.use(v0.call_fn(1, 2)) == 3

    v1_ref = weave.versions(versioned_op.op_def)[0]
    v1 = v1_ref.get()
    assert weave.use(v1.call_fn(1, 2)) == -1

    # TODO:
    # - test that previous versions hit memoize cache correctly
    # TODO: show that you can use weave.get(<op_name>/<version>) to get an op as well.
