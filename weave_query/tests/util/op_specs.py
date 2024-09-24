import dataclasses
import datetime
import typing

import weave
from weave.legacy.weave import op_def, ops_primitives
from weave.legacy.weave.language_features.tagging import tagged_value_type
from weave.legacy.weave.timestamp import PY_DATETIME_MAX_MS, PY_DATETIME_MIN_MS

from .concrete_tagged_value import TaggedValue


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
    list_list_op: bool = False


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

number_mul = OpSpec(
    op=ops_primitives.Number.__mul__,
    kind=OpKind(arity=2, commutative=True),
    test_cases=[
        OpSpecTestCase(
            input=(1, 2),
            expected=2,
            expected_type=weave.types.Number(),
        ),
        OpSpecTestCase(
            input=(-1, 2),
            expected=-2,
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

numbers_min = OpSpec(
    op=ops_primitives.numbers_min,
    kind=OpKind(arity=1, list_op=True),
    test_cases=[
        OpSpecTestCase(
            input=([-10, -99, -100],),
            expected=-100,
            expected_type=weave.types.Number(),
        ),
        OpSpecTestCase(
            input=([0, 1, 3],),
            expected=0,
            expected_type=weave.types.Number(),
        ),
    ],
)

numbers_avg = OpSpec(
    op=ops_primitives.numbers_avg,
    kind=OpKind(arity=1, list_op=True),
    test_cases=[
        OpSpecTestCase(
            input=([-10, -100],),
            expected=-55.0,
            expected_type=weave.types.Float(),
        ),
        OpSpecTestCase(
            input=([1, 3],),
            expected=2.0,
            expected_type=weave.types.Float(),
        ),
    ],
)

numbers_sum = OpSpec(
    op=ops_primitives.numbers_sum,
    kind=OpKind(arity=1, list_op=True),
    test_cases=[
        OpSpecTestCase(
            input=([-10, -99, -100],),
            expected=-209,
            expected_type=weave.types.Number(),
        ),
        OpSpecTestCase(
            input=([0, 1, 3],),
            expected=4,
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
        # I didn't implement negative indexing or list indexing in vectorized
        # cases yet
        # TODO: fix!
        # OpSpecTestCase(
        #     input=([1, 2, 3], -1),
        #     expected=3,
        #     expected_type=weave.types.Number(),
        # ),
        # OpSpecTestCase(
        #     input=([1, 2, 3], [0, -1, 5, None]),
        #     expected=3,
        #     expected_type=weave.types.List(weave.types.Number()),
        # ),
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

join_all = OpSpec(
    op=ops_primitives.join_all,
    kind=OpKind(arity=3, list_list_op=True, uniform_input_types=False),
    test_cases=[
        OpSpecTestCase(
            input=(
                [[{"a": 5, "b": 6}, {"a": 7, "b": 9}], [{"a": 5, "b": 8}]],
                lambda x: x["a"],
                False,
            ),
            expected=[TaggedValue({"joinObj": 5}, {"a": [5, 5], "b": [6, 8]})],
            expected_type=weave.types.List(
                tagged_value_type.TaggedValueType(
                    weave.types.TypedDict({"joinObj": weave.types.Int()}),
                    weave.types.TypedDict(
                        {
                            "a": weave.types.List(
                                weave.types.optional(weave.types.Int())
                            ),
                            "b": weave.types.List(
                                weave.types.optional(weave.types.Int())
                            ),
                        }
                    ),
                )
            ),
        ),
        # 'b' will end up a union of TypedDict and Int
        OpSpecTestCase(
            input=(
                [
                    [{"a": 5, "b": 6}, {"a": 7, "b": 9}],
                    [{"a": 5, "b": {"j": 12, "k": 13}}],
                ],
                lambda x: x["a"],
                False,
            ),
            expected=[
                TaggedValue({"joinObj": 5}, {"a": [5, 5], "b": [6, {"j": 12, "k": 13}]})
            ],
            expected_type=weave.types.List(
                tagged_value_type.TaggedValueType(
                    weave.types.TypedDict({"joinObj": weave.types.Int()}),
                    weave.types.TypedDict(
                        {
                            "a": weave.types.List(
                                weave.types.optional(weave.types.Int())
                            ),
                            "b": weave.types.List(
                                weave.types.optional(
                                    weave.types.UnionType(
                                        weave.types.Int(),
                                        weave.types.TypedDict(
                                            {
                                                "j": weave.types.Int(),
                                                "k": weave.types.Int(),
                                            }
                                        ),
                                    )
                                )
                            ),
                        }
                    ),
                )
            ),
        ),
    ],
)


dropna = OpSpec(
    op=ops_primitives.List.dropna,
    kind=OpKind(arity=1, list_op=True),
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

number_equal = OpSpec(
    op=ops_primitives.Number.__eq__,
    kind=OpKind(arity=2, commutative=True),
    test_cases=[
        OpSpecTestCase(
            input=(1, 1),
            expected=True,
            expected_type=weave.types.Boolean(),
        ),
        OpSpecTestCase(
            input=(1, 2),
            expected=False,
            expected_type=weave.types.Boolean(),
        ),
        OpSpecTestCase(
            input=(1, None),
            expected=False,
            expected_type=weave.types.Boolean(),
        ),
        OpSpecTestCase(
            input=(None, None),
            expected=True,
            expected_type=weave.types.Boolean(),
        ),
        OpSpecTestCase(
            input=(None, 1),
            expected=False,
            expected_type=weave.types.Boolean(),
        ),
    ],
)


string_equal = OpSpec(
    op=ops_primitives.String.__eq__,
    kind=OpKind(arity=2, commutative=True),
    test_cases=[
        OpSpecTestCase(
            input=("a", "a"),
            expected=True,
            expected_type=weave.types.Boolean(),
        ),
        OpSpecTestCase(
            input=("a", "b"),
            expected=False,
            expected_type=weave.types.Boolean(),
        ),
        OpSpecTestCase(
            input=("a", None),
            expected=False,
            expected_type=weave.types.Boolean(),
        ),
        OpSpecTestCase(
            input=(None, None),
            expected=True,
            expected_type=weave.types.Boolean(),
        ),
        OpSpecTestCase(
            input=(None, "a"),
            expected=False,
            expected_type=weave.types.Boolean(),
        ),
    ],
)


boolean_equal = OpSpec(
    op=ops_primitives.Boolean.bool_equals,
    kind=OpKind(arity=2, commutative=True),
    test_cases=[
        OpSpecTestCase(
            input=(True, True),
            expected=True,
            expected_type=weave.types.Boolean(),
        ),
        OpSpecTestCase(
            input=(True, False),
            expected=False,
            expected_type=weave.types.Boolean(),
        ),
        OpSpecTestCase(
            input=(True, None),
            expected=False,
            expected_type=weave.types.Boolean(),
        ),
        OpSpecTestCase(
            input=(None, None),
            expected=True,
            expected_type=weave.types.Boolean(),
        ),
        OpSpecTestCase(
            input=(None, True),
            expected=False,
            expected_type=weave.types.Boolean(),
        ),
    ],
)


OP_TEST_SPECS = [
    number_add,
    number_sub,
    number_mul,
    string_add,
    numbers_max,
    numbers_min,
    numbers_avg,
    numbers_sum,
    number_to_timestamp,
    index,
    join_all,
    dropna,
    number_equal,
    string_equal,
    boolean_equal,
]
