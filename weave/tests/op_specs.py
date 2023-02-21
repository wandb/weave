import dataclasses
import typing

import weave
from weave import op_def
from weave import ops_primitives


@dataclasses.dataclass
class OpSpecTestCase:
    input: tuple[typing.Any, ...]
    expected: typing.Any
    expected_type: weave.types.Type


@dataclasses.dataclass
class OpKind:
    arity: int
    uniform_input_types: bool = True
    commutative: bool = False
    list_op: bool = False


@dataclasses.dataclass
class OpSpec:
    op: op_def.OpDef
    test_cases: list[OpSpecTestCase]
    kind: OpKind


string_add = OpSpec(
    op=ops_primitives.String.__add__,
    kind=OpKind(arity=2, commutative=False),
    test_cases=[
        OpSpecTestCase(
            input=("a", "b"),
            expected="ab",
            expected_type=weave.types.String(),
        ),
        OpSpecTestCase(
            input=("b", "a"),
            expected="ba",
            expected_type=weave.types.String(),
        ),
        OpSpecTestCase(
            input=("", "b"),
            expected="b",
            expected_type=weave.types.String(),
        ),
        OpSpecTestCase(
            input=("b", ""),
            expected="b",
            expected_type=weave.types.String(),
        ),
    ],
)

number_add = OpSpec(
    op=ops_primitives.Number.__add__,
    kind=OpKind(arity=2, commutative=True),
    test_cases=[
        OpSpecTestCase(
            input=(1, 2),
            expected=3,
            expected_type=weave.types.Number(),
        ),
        OpSpecTestCase(
            input=(-1, 2),
            expected=1,
            expected_type=weave.types.Number(),
        ),
    ],
)

number_sub = OpSpec(
    op=ops_primitives.Number.__sub__,
    kind=OpKind(arity=2, commutative=False),
    test_cases=[
        OpSpecTestCase(
            input=(1, 2),
            expected=-1,
            expected_type=weave.types.Number(),
        ),
        OpSpecTestCase(
            input=(2, 1),
            expected=1,
            expected_type=weave.types.Number(),
        ),
        OpSpecTestCase(
            input=(-1, 2),
            expected=-3,
            expected_type=weave.types.Number(),
        ),
        OpSpecTestCase(
            input=(2, -1),
            expected=3,
            expected_type=weave.types.Number(),
        ),
    ],
)

numbers_max = OpSpec(
    op=ops_primitives.numbers_max,
    kind=OpKind(arity=1, list_op=True),
    test_cases=[
        OpSpecTestCase(
            input=([-10, -99, -100],),
            expected=-10,
            expected_type=weave.types.Number(),
        ),
        OpSpecTestCase(
            input=([0, 1, 3],),
            expected=3,
            expected_type=weave.types.Number(),
        ),
    ],
)

index = OpSpec(
    op=ops_primitives.List.__getitem__,
    kind=OpKind(arity=2, list_op=True, uniform_input_types=False),
    test_cases=[
        OpSpecTestCase(
            input=([1, 2, 3], 0),
            expected=1,
            expected_type=weave.types.Number(),
        ),
        OpSpecTestCase(
            input=([1, 2, 3], 2),
            expected=3,
            expected_type=weave.types.Number(),
        ),
        OpSpecTestCase(
            input=([-5, -6], 2),
            expected=None,
            expected_type=weave.types.optional(weave.types.Number()),
        ),
        OpSpecTestCase(
            input=([], 0),
            expected=None,
            expected_type=weave.types.NoneType(),
        ),
    ],
)

OP_TEST_SPECS = [number_add, number_sub, string_add, numbers_max, index]
