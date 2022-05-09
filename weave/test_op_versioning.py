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

    v0_ref = weave.versions(versioned_op)[0]
    v0 = v0_ref.get()
    assert weave.use(v0.call_fn(1, 2)) == 3

    # This should refer to v1, even though we just loaded v0
    v_latest = weave.use(weave.get("op-op-versioned_op/latest"))
    assert weave.use(v_latest.call_fn(4, 20)) == -16

    v1_ref = weave.versions(versioned_op)[1]
    v1 = v1_ref.get()
    assert weave.use(v1.call_fn(1, 2)) == -1

    v0_again = weave.use(weave.get("op-op-versioned_op/" + v0.version))
    assert weave.use(v0_again.call_fn(5, 6)) == 11
