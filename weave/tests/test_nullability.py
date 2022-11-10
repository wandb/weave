import typing
import weave


@weave.op()
def no_arg_op() -> int:
    return 1


@weave.op()
def int_arg_op(a: int) -> int:
    return a + 1


@weave.op()
def int_args_op(a: int, b: int) -> int:
    return a + b


@weave.op()
def null_consuming_op(a: typing.Optional[int], b: int) -> int:
    if a == None:
        return b * 10
    return a + b  # type: ignore


def test_basic_nullability():
    b = weave.save(2)
    maybe_int = weave.save(
        weave.graph.ConstNode(weave.types.optional(weave.types.Int()), 1)
    )
    null_int = weave.save(
        weave.graph.ConstNode(weave.types.optional(weave.types.Int()), None)
    )

    assert weave.use(no_arg_op()) == 1

    assert weave.use(int_arg_op(b)) == 3
    assert weave.use(int_arg_op(maybe_int)) == 2
    assert weave.use(int_arg_op(null_int)) == None

    assert weave.use(int_args_op(b, b)) == 4
    assert weave.use(int_args_op(maybe_int, b)) == 3
    assert weave.use(int_args_op(null_int, b)) == None

    assert weave.use(null_consuming_op(b, b)) == 4
    assert weave.use(null_consuming_op(maybe_int, b)) == 3
    assert weave.use(null_consuming_op(null_int, b)) == 20


def test_basic_nullability_in_mappability():
    b_arr = weave.save([2])
    maybe_int_arr = weave.save(
        weave.graph.ConstNode(
            weave.types.List(weave.types.optional(weave.types.Int())), [1, None]
        )
    )

    assert weave.use(int_arg_op(b_arr)) == [3]
    assert weave.use(int_arg_op(maybe_int_arr)) == [2, None]

    assert weave.use(int_args_op(b_arr, 2)) == [4]
    assert weave.use(int_args_op(maybe_int_arr, 2)) == [3, None]

    assert weave.use(null_consuming_op(b_arr, 2)) == [4]
    assert weave.use(null_consuming_op(maybe_int_arr, 2)) == [3, 20]
