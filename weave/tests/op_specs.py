import dataclasses
import datetime
import typing

import weave
from weave import op_def
from weave import ops_primitives
from weave.timestamp import PY_DATETIME_MAX_MS, PY_DATETIME_MIN_MS


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


dropna = OpSpec(
    op=ops_primitives.List.dropna,
    kind=OpKind(arity=1),
    test_cases=[
        OpSpecTestCase(
            input=([1, 2, 3],),
            expected=[1, 2, 3],
            expected_type=weave.types.List(weave.types.Int()),
        ),
        OpSpecTestCase(
            input=([1, None, 3],),
            expected=[1, 3],
            expected_type=weave.types.List(weave.types.Int()),
        ),
        OpSpecTestCase(
            input=([None, None, None],),
            expected=[],
            expected_type=weave.types.List(weave.types.NoneType()),
        ),
    ],
)

number_to_timestamp = OpSpec(
    op=ops_primitives.Number.to_timestamp,
    kind=OpKind(arity=1),
    test_cases=[
        # Current Time
        OpSpecTestCase(
            input=(1677098489000,),
            expected=datetime.datetime.fromtimestamp(1677098489, datetime.timezone.utc),
            expected_type=weave.types.Timestamp(),
        ),
        # Zero Time
        OpSpecTestCase(
            input=(0,),
            expected=datetime.datetime.fromtimestamp(0, datetime.timezone.utc),
            expected_type=weave.types.Timestamp(),
        ),
        # Negative Time
        OpSpecTestCase(
            input=(-1677098489000,),
            expected=datetime.datetime.fromtimestamp(
                -1677098489, datetime.timezone.utc
            ),
            expected_type=weave.types.Timestamp(),
        ),
        # Small Value
        OpSpecTestCase(
            input=(1000,),
            expected=datetime.datetime.fromtimestamp(1, datetime.timezone.utc),
            expected_type=weave.types.Timestamp(),
        ),
        # Large Value
        OpSpecTestCase(
            input=(PY_DATETIME_MAX_MS,),
            expected=datetime.datetime.fromtimestamp(
                PY_DATETIME_MAX_MS / 1000, datetime.timezone.utc
            ),
            expected_type=weave.types.Timestamp(),
        ),
        # Large Value (in nanoseconds)
        OpSpecTestCase(
            input=(PY_DATETIME_MAX_MS + 12345,),
            expected=datetime.datetime.fromtimestamp(
                ((PY_DATETIME_MAX_MS + 12345) // 1000) / 1000, datetime.timezone.utc
            ),
            expected_type=weave.types.Timestamp(),
        ),
        # Large Negative Value
        OpSpecTestCase(
            input=(PY_DATETIME_MIN_MS,),
            expected=datetime.datetime.fromtimestamp(
                PY_DATETIME_MIN_MS / 1000, datetime.timezone.utc
            ),
            expected_type=weave.types.Timestamp(),
        ),
        # Large Negative Value (in nano seconds)
        OpSpecTestCase(
            input=(PY_DATETIME_MIN_MS - 12345,),
            expected=datetime.datetime.fromtimestamp(
                ((PY_DATETIME_MIN_MS - 12345) // 1000) / 1000, datetime.timezone.utc
            ),
            expected_type=weave.types.Timestamp(),
        ),
        # Float Value (Drops Fractional Part)
        OpSpecTestCase(
            input=(1677098489215.025,),
            expected=datetime.datetime.fromtimestamp(
                1677098489.215, datetime.timezone.utc
            ),
            expected_type=weave.types.Timestamp(),
        ),
    ],
)


OP_TEST_SPECS = [
    number_add,
    number_sub,
    string_add,
    numbers_max,
    number_to_timestamp,
    index,
    dropna,
]
