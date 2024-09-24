# Automatic op testing.
#
# This automatically tests all ops defined in op_specs.py. We generate a set
# of variant test cases for every op. It is easy to add checks like
# "binary commutative ops should be produce None when vectorized with a null
# scalar as the other argument".

import dataclasses
import itertools
import typing

import pytest

import weave
from weave.legacy.weave import (
    graph,
    graph_debug,
    language_nullability,
    op_def,
    ops_arrow,
    ops_primitives,
    storage,
    weave_internal,
)
from weave.legacy.weave.language_features.tagging import make_tag_getter_op
from weave.legacy.weave.language_features.tagging.tagged_value_type import (
    TaggedValueType,
)

from ...legacy.weave import registry_mem
from weave.legacy.tests.util.concrete_tagged_value import (
    TaggedValue,
    concrete_from_tagstore,
    concrete_to_tagstore,
)
from weave.legacy.tests.util.op_specs import OP_TEST_SPECS, OpSpec, OpSpecTestCase


def assert_equal_with_tags(node: graph.Node, v: typing.Any, expected: typing.Any):
    v = concrete_from_tagstore(v)
    if isinstance(expected, TaggedValue):
        # Nones are not tagged
        if v != None:
            assert isinstance(v, TaggedValue)
            assert expected.tag == v.tag
            v = v.value
        expected = expected.value

    if isinstance(v, ops_arrow.ArrowWeaveList):
        assert isinstance(expected, ops_arrow.ArrowWeaveList)
        actual_py = v.to_pylist_raw()
        expected_py = expected.to_pylist_raw()
        assert actual_py == expected_py
        # We can't check the arrow type if we expect all Nones, because we pass
        # a python list in as the expectation right now. And in arrow you can have
        # Nones of any type.
        if not all(x is None for x in expected):
            assert v._arrow_data.type == expected._arrow_data.type
        # TODO: this check is too loose, it should be type equality. But
        # we currently aren't specific enough in some ops, or have mistmatches
        # between python and arrow
        assert expected.object_type.assign_type(v.object_type)
    else:
        assert v == expected


def assert_fn_vectorized(fn_node: graph.Node) -> graph.Node:
    vec_fn_node = ops_arrow.vectorize(fn_node)

    def assert_node_vectorized(n: graph.Node):
        if isinstance(n, graph.OutputNode):
            assert isinstance(
                n.type, ops_arrow.ArrowWeaveListType
            ), f"fn_node {graph_debug.node_expr_str_full(fn_node)} is not fully vectorized. Vectorized as {graph_debug.node_expr_str_full(vec_fn_node)}. Node {graph_debug.node_expr_str_full(n)} is of type {n.type}. All nodes within a vectorized function should be ArrowWeaveListType."

    graph.map_nodes_top_level([vec_fn_node], assert_node_vectorized)
    return vec_fn_node


def check_case(called: graph.Node, result_type: weave.types.Type, result: typing.Any):
    assert result_type.assign_type(
        called.type
    ), f"Expected op output type: {result_type}, but got {called.type}"

    # This is a way to save the final output, preserving tags.
    result_ref = weave.use(weave.legacy.weave.ops.save_to_ref(called, None))
    if result_ref == None:
        actual_result = None
    else:
        actual_result = storage.get(str(result_ref))
    assert_equal_with_tags(called, actual_result, result)

    # # We can't check the type of the output we received, because execution
    # # doesn't produce tags directly. But since we know result was equal
    # # to expectation from above, we can check that the type of the
    # # expectation instead.
    actual_result_type = weave.type_of(concrete_to_tagstore(result))
    # # TODO: this check is too loose, it should be type equality. But
    # # we currently aren't specific enough in some ops, or have mistmatches
    # # between python and arrow
    assert result_type.assign_type(
        actual_result_type
    ), f"{graph_debug.node_expr_str_full(called)} produced type {actual_result_type}, but expected type {result_type}"


def call(op_def: op_def.OpDef, args: typing.Any):
    inputs = [concrete_to_tagstore(it) for it in args]
    # We have to save inputs to make the tags available inside the executor.
    # Users will never have to do this since they don't interact with tests
    # directly, but it slows the test down since saving writes to disk.
    saved_inputs = [weave.save(it) if not callable(it) else it for it in inputs]

    return op_def(*saved_inputs)


class NoValue:
    pass


@dataclasses.dataclass
class OpTestCase:
    name: list[str]

    def check(self):
        raise NotImplementedError()


@dataclasses.dataclass
class OpTestCaseStandard(OpTestCase):
    op_def: op_def.OpDef
    input: tuple[typing.Any, ...]
    expected_type: typing.Any
    expected: typing.Any

    def variant(
        self,
        name: str,
        input: typing.Union[NoValue, tuple[typing.Any, ...]] = NoValue(),
        expected_type: typing.Union[NoValue, typing.Any] = NoValue(),
        expected: typing.Union[NoValue, typing.Any] = NoValue(),
    ):
        return OpTestCaseStandard(
            name=self.name + [name],
            op_def=self.op_def,
            input=self.input if isinstance(input, NoValue) else input,
            expected_type=self.expected_type
            if isinstance(expected_type, NoValue)
            else expected_type,
            expected=self.expected if isinstance(expected, NoValue) else expected,
        )

    def vecdim0_variant(
        self,
        name: str,
        input: typing.Union[NoValue, tuple[typing.Any, ...]] = NoValue(),
        expected_type: typing.Union[NoValue, typing.Any] = NoValue(),
        expected: typing.Union[NoValue, typing.Any] = NoValue(),
    ):
        return OpTestCaseVecDim0(
            name=self.name + [name],
            op_def=self.op_def,
            input=self.input if isinstance(input, NoValue) else input,
            expected_type=self.expected_type
            if isinstance(expected_type, NoValue)
            else expected_type,
            expected=self.expected if isinstance(expected, NoValue) else expected,
        )

    def vecdim1_variant(
        self,
        name: str,
        input: typing.Union[NoValue, tuple[typing.Any, ...]] = NoValue(),
        expected_type: typing.Union[NoValue, typing.Any] = NoValue(),
        expected: typing.Union[NoValue, typing.Any] = NoValue(),
    ):
        return OpTestCaseVecDim1(
            name=self.name + [name],
            op_def=self.op_def,
            input=self.input if isinstance(input, NoValue) else input,
            expected_type=self.expected_type
            if isinstance(expected_type, NoValue)
            else expected_type,
            expected=self.expected if isinstance(expected, NoValue) else expected,
        )

    def check(self):
        check_case(
            call(self.op_def, self.input),
            result_type=self.expected_type,
            result=self.expected,
        )


def convert_expected_to_arrow(
    expected_type: weave.types.Type, expected: typing.Any
) -> tuple[weave.types.Type, typing.Any]:
    if isinstance(expected_type, weave.types.List):
        assert isinstance(expected, list)
        arrow_type = ops_arrow.ArrowWeaveListType(expected_type.object_type)
        arrow_list = ops_arrow.to_arrow(concrete_to_tagstore(expected))
        # We override the object type in the expected value, to be the declared expected
        # type. The arrow list value may have a type that is too narrow for checking
        # (right now ArrowWeaveLists constructed inside op resolvers tend to use the
        # input type logic, which creates wider types than doing a type_of operation would)
        arrow_list.object_type = arrow_type.object_type
        return arrow_type, arrow_list
    if isinstance(expected_type, TaggedValueType):
        assert isinstance(expected, TaggedValue)
        expected_value_type, expected_value = convert_expected_to_arrow(
            expected_type.value, expected.value
        )
        return TaggedValueType(expected_type.tag, expected_value_type), TaggedValue(
            expected.tag, expected_value
        )
    return expected_type, expected


@dataclasses.dataclass
class OpTestCaseVecDim0(OpTestCaseStandard):
    """Tests that a list op has a vectorized equivalent."""

    op_def: op_def.OpDef
    input: tuple[typing.Any, ...]
    expected_type: typing.Any
    expected: typing.Any

    def check(self):
        inputs = [concrete_to_tagstore(it) for it in self.input]
        inputs[0] = ops_arrow.to_arrow(inputs[0])
        inputs = [
            weave.save(input) if not callable(input) else input for input in inputs
        ]
        called = getattr(inputs[0], self.op_def.simple_name)(*inputs[1:])
        called_op_name = called.from_op.name
        called_op_def = registry_mem.memory_registry.get_op(called_op_name)
        assert isinstance(
            list(called_op_def.input_type.arg_types.values())[0],
            ops_arrow.ArrowWeaveListType,
        )
        expected_type, expected = convert_expected_to_arrow(
            self.expected_type, self.expected
        )
        check_case(
            called,
            result_type=expected_type,
            result=expected,
        )


@dataclasses.dataclass
class OpTestCaseVecDim1(OpTestCaseStandard):
    """Tests that a list op has a vectorized equivalent for second dim (joinall/concat)."""

    op_def: op_def.OpDef
    input: tuple[typing.Any, ...]
    expected_type: typing.Any
    expected: typing.Any

    def check(self):
        inputs = [concrete_to_tagstore(it) for it in self.input]
        inputs[0] = [ops_arrow.to_arrow(i) for i in inputs[0]]
        if isinstance(self.input[0], TaggedValue):
            inputs[0] = concrete_to_tagstore(TaggedValue(self.input[0].tag, inputs[0]))
        inputs = [
            weave.save(input) if not callable(input) else input for input in inputs
        ]
        called = getattr(inputs[0], self.op_def.simple_name)(*inputs[1:])
        assert ops_arrow.ArrowWeaveListType().assign_type(called.type)
        expected_type, expected = convert_expected_to_arrow(
            self.expected_type, self.expected
        )
        check_case(
            called,
            result_type=expected_type,
            result=expected,
        )


@dataclasses.dataclass
class OpTestCaseVector(OpTestCase):
    """Test there is a vectorized version that handles all inputs as vectors."""

    op_def: op_def.OpDef
    input_vecs: tuple[list[typing.Any], ...]
    expected_object_type: typing.Any
    expected: typing.Any

    def variant(
        self,
        name: str,
        input_vecs: typing.Union[NoValue, tuple[list[typing.Any], ...]] = NoValue(),
        expected_object_type: typing.Union[NoValue, typing.Any] = NoValue(),
        expected: typing.Union[NoValue, typing.Any] = NoValue(),
    ):
        return OpTestCaseVector(
            name=self.name + [name],
            op_def=self.op_def,
            input_vecs=self.input_vecs
            if isinstance(input_vecs, NoValue)
            else input_vecs,
            expected_object_type=self.expected_object_type
            if isinstance(expected_object_type, NoValue)
            else expected_object_type,
            expected=self.expected if isinstance(expected, NoValue) else expected,
        )

    def check(self):
        input_vars = {
            k: weave.type_of(v).object_type
            for k, v in zip(self.op_def.input_type.arg_types, self.input_vecs)
        }
        op_fn = weave_internal.define_fn(input_vars, lambda *args: self.op_def(*args))
        vec_op_fn = assert_fn_vectorized(op_fn.val)
        called = weave_internal.call_fn(
            vec_op_fn,
            {
                k: ops_arrow.to_weave_arrow(v)
                for k, v in zip(input_vars, self.input_vecs)
            },
        )
        check_case(
            called,
            result_type=ops_arrow.ArrowWeaveListType(self.expected_object_type),
            result=ops_arrow.to_arrow(self.expected),
        )


@dataclasses.dataclass
class OpTestCaseBinaryVectorScalar(OpTestCase):
    """Test binary op vectorizes with (vec, scalar) or (scalar, vec) call"""

    op_def: op_def.OpDef
    vec: list[typing.Any]
    scalar: typing.Any
    vec_first: bool
    expected_object_type: typing.Any
    expected: typing.Any

    def variant(
        self,
        name: str,
        vec: typing.Union[NoValue, list[typing.Any]] = NoValue(),
        scalar: typing.Union[NoValue, typing.Any] = NoValue(),
        vec_first: typing.Union[NoValue, bool] = NoValue(),
        expected_object_type: typing.Union[NoValue, typing.Any] = NoValue(),
        expected: typing.Union[NoValue, typing.Any] = NoValue(),
    ):
        return OpTestCaseBinaryVectorScalar(
            name=self.name + [name],
            op_def=self.op_def,
            vec=self.vec if isinstance(vec, NoValue) else vec,
            scalar=self.scalar if isinstance(scalar, NoValue) else scalar,
            vec_first=self.vec_first if isinstance(vec_first, NoValue) else vec_first,
            expected_object_type=self.expected_object_type
            if isinstance(expected_object_type, NoValue)
            else expected_object_type,
            expected=self.expected if isinstance(expected, NoValue) else expected,
        )

    def check(self):
        # Check the python listmap version
        map_fn = (
            lambda x: self.op_def(x, self.scalar)
            if self.vec_first
            else self.op_def(self.scalar, x)
        )
        check_case(
            ops_primitives.List._listmap(self.vec, map_fn),
            result_type=weave.types.List(self.expected_object_type),
            result=self.expected,
        )
        # Check arrow version
        arrow_vec = ops_arrow.to_arrow(self.vec)
        called = call(ops_arrow.ops.map, (arrow_vec, map_fn))
        # ensure it vectorized
        assert_fn_vectorized(called.from_op.inputs["map_fn"].val)
        check_case(
            called,
            result_type=ops_arrow.ArrowWeaveListType(self.expected_object_type),
            result=ops_arrow.to_arrow(self.expected),
        )


@dataclasses.dataclass
class OpTestCaseBinaryVectorVector(OpTestCase):
    """Test binary op vectorizes with (a, a) call"""

    op_def: op_def.OpDef
    arity: int
    vec: list[typing.Any]

    def variant(
        self,
        name: str,
        vec: typing.Union[NoValue, list[typing.Any]] = NoValue(),
    ):
        return OpTestCaseBinaryVectorVector(
            name=self.name + [name],
            op_def=self.op_def,
            arity=self.arity,
            vec=self.vec if isinstance(vec, NoValue) else vec,
        )

    def check(self):
        def map_fn(item):
            return self.op_def(*tuple(item for i in range(self.arity)))

        listmap_called = call(ops_primitives.List._listmap, (self.vec, map_fn))
        listmap_result = weave.use(listmap_called)
        vec_called = call(ops_arrow.ops.map, (ops_arrow.to_arrow(self.vec), map_fn))
        assert_fn_vectorized(vec_called.from_op.inputs["map_fn"].val)
        vec_result = weave.use(vec_called)
        assert listmap_result == vec_result.to_pylist_tagged()


def make_standard_variants(
    op_test_def: OpSpec, test_case: OpSpecTestCase, test_case_index: int
) -> list[OpTestCaseStandard]:
    op_name = op_test_def.op.name
    base = OpTestCaseStandard(
        [op_name, f"case{test_case_index}"],
        op_test_def.op,
        test_case.input,
        test_case.expected_type,
        test_case.expected,
    )
    base_variants: list[OpTestCaseStandard] = []
    # Check the case itself
    base_variants.append(base)

    # Check commutativity
    if op_test_def.kind.arity == 2 and op_test_def.kind.commutative:
        base_variants.append(base.variant("commutative", input=test_case.input[::-1]))

    # the op should handle None in any position, returning None.
    is_null_consuming = not language_nullability.should_force_none_result(
        {"first_arg": None}, op_test_def.op
    )

    if not is_null_consuming:
        inputs = list(test_case.input)
        inputs[0] = None

        base_variants.append(
            base.variant(
                "arg0-none",
                input=tuple(inputs),
                expected_type=weave.types.optional(test_case.expected_type),
                expected=None,
            )
        )
        if op_test_def.kind.arity == 2:
            base_variants.append(
                base.variant(
                    "arg1-none",
                    input=(test_case.input[0], None),
                    expected_type=weave.types.optional(test_case.expected_type),
                    expected=None,
                )
            )

    # Tags in first position are flowed to output.
    inputs = list(test_case.input)
    inputs[0] = TaggedValue({"a": 5}, inputs[0])
    base_variants.append(
        base.variant(
            "arg0-tag",
            input=tuple(inputs),
            expected_type=TaggedValueType(
                weave.types.TypedDict({"a": weave.types.Int()}),
                test_case.expected_type,
            ),
            expected=TaggedValue({"a": 5}, test_case.expected),
        )
    )

    if op_test_def.kind.arity == 2:
        # Tags in second position are dropped
        base_variants.append(
            base.variant(
                "rhs-tag",
                input=(
                    test_case.input[0],
                    TaggedValue({"a": 5}, test_case.input[1]),
                ),
            )
        )

    return base_variants


def make_standard_vector_variants(
    op_test_def: OpSpec,
) -> list[OpTestCaseVector]:
    op_name = op_test_def.op.name
    input_vecs = [
        [tc.input[i] for tc in op_test_def.test_cases]
        for i in range(op_test_def.kind.arity)
    ]
    variants = []

    base_variant = OpTestCaseVector(
        [op_name, "vector"],
        op_test_def.op,
        tuple(input_vecs),
        weave.types.union(*[tc.expected_type for tc in op_test_def.test_cases]),
        [tc.expected for tc in op_test_def.test_cases],
    )
    variants.append(base_variant)

    input_vecs_with_arg0_nones = []
    input_vecs_with_arg0_nones.append(input_vecs[0] + [None] * len(input_vecs[0]))
    if op_test_def.kind.arity == 2:
        input_vecs_with_arg0_nones.append(input_vecs[1] * 2)

    is_null_consuming = not language_nullability.should_force_none_result(
        {"first_arg": None}, op_test_def.op
    )

    if not is_null_consuming:
        variants.append(
            base_variant.variant(
                "arg0-none",
                input_vecs=tuple(input_vecs_with_arg0_nones),
                expected_object_type=weave.types.optional(
                    base_variant.expected_object_type
                ),
                expected=base_variant.expected + [None] * len(input_vecs[0]),
            )
        )

        if op_test_def.kind.arity == 2:
            input_vecs_with_arg1_nones = []
            input_vecs_with_arg1_nones.append(input_vecs[0] * 2)
            input_vecs_with_arg1_nones.append(
                input_vecs[1] + [None] * len(input_vecs[1])
            )
            variants.append(
                base_variant.variant(
                    "arg1-none",
                    input_vecs=tuple(input_vecs_with_arg1_nones),
                    expected_object_type=weave.types.optional(
                        base_variant.expected_object_type
                    ),
                    expected=base_variant.expected + [None] * len(input_vecs[1]),
                )
            )

    return variants


def make_binary_vectorscalar_variants(
    op_test_def: OpSpec,
    vector_position: typing.Union[typing.Literal["lhs"], typing.Literal["rhs"]],
) -> list[OpTestCaseBinaryVectorScalar]:
    op_name = op_test_def.op.name
    if vector_position == "lhs":
        vec_index = 0
        scalar_index = 1
    else:
        vec_index = 1
        scalar_index = 0

    variants: list[OpTestCaseBinaryVectorScalar] = []

    key_fn = lambda x: str(x.input[scalar_index])
    scalar_grouped = itertools.groupby(
        sorted(op_test_def.test_cases, key=key_fn), key=key_fn
    )
    scalar_groups: list[list[OpSpecTestCase]] = []
    for k, v in scalar_grouped:
        scalar_groups.append(list(v))
    groups_of_more_than_one = [g for g in scalar_groups if len(g) > 1]
    assert (
        len(groups_of_more_than_one) > 0
    ), f"You must provide at least two test cases with the same {vector_position.upper()} for op: {op_name}"

    for i, tcs in enumerate(groups_of_more_than_one):
        vec = [tc.input[vec_index] for tc in tcs]
        scalar = tcs[0].input[scalar_index]
        expected_object_type = weave.types.union(*[tc.expected_type for tc in tcs])
        result = [tc.expected for tc in tcs]
        vecgroup_variants: list[OpTestCaseBinaryVectorScalar] = []

        base_vec = OpTestCaseBinaryVectorScalar(
            [op_name, f"vector-{vector_position}", f"casegroup{i}"],
            op_test_def.op,
            vec=vec,
            scalar=scalar,
            vec_first=vector_position == "lhs",
            expected_object_type=expected_object_type,
            expected=result,
        )
        vecgroup_variants.append(base_vec)

        is_null_consuming = not language_nullability.should_force_none_result(
            {"first_arg": None}, op_test_def.op
        )

        if not is_null_consuming:
            vecgroup_variants.append(
                base_vec.variant(
                    "vec-with-none",
                    vec=vec + [None],
                    expected_object_type=weave.types.optional(expected_object_type),
                    expected=result + [None],
                )
            )

            if vector_position == "lhs":
                # We can't use the variant when vector_position is rhs, because
                # nullability means we'll just return None for the None scalar, not
                # using our vectorized op.
                # TODO: fix! We should return a vector of None in this case.
                vecgroup_variants.append(
                    base_vec.variant(
                        "scalar-none",
                        scalar=None,
                        expected_object_type=weave.types.optional(expected_object_type),
                        expected=[None] * len(vec),
                    )
                )

        variants.extend(vecgroup_variants)

    return variants


def is_all_none(x):
    if isinstance(x, list):
        return all(is_all_none(i) for i in x)
    elif isinstance(x, TaggedValue):
        return is_all_none(x.value)
    else:
        return x == None


def make_op_variants(op_test_def: OpSpec):
    variants: list[OpTestCase] = []
    op_name = op_test_def.op.name

    # standard, non-vectorized variants
    for i, test_case in enumerate(op_test_def.test_cases):
        base_variants = make_standard_variants(op_test_def, test_case, i)

        variants.extend(base_variants)

        # Add vectorized dim0 variants of all base_variants for list ops
        if op_test_def.kind.list_op:
            for variant in base_variants:
                # Don't need to test when first arg is None
                if not is_all_none(variant.input[0]):
                    variants.append(variant.vecdim0_variant("vecdim0"))
        if op_test_def.kind.list_list_op:
            for variant in base_variants:
                # Don't need to test when first arg is None
                if not is_all_none(variant.input[0]):
                    variants.append(variant.vecdim1_variant("vecdim1"))

    # All test cases in one vectorized call
    if op_test_def.kind.arity <= 2:
        variants.extend(make_standard_vector_variants(op_test_def))

    # (a, a) form where a is a vector
    if op_test_def.kind.arity == 2 and op_test_def.kind.uniform_input_types:
        all_lhs = [tc.input[0] for tc in op_test_def.test_cases]
        vecvec = OpTestCaseBinaryVectorVector(
            [op_name, "vecvec"], op_test_def.op, op_test_def.kind.arity, all_lhs
        )
        variants.append(vecvec)

    # (vec, scalar) and (scalar, vec) variants
    if op_test_def.kind.arity == 2:
        vec_variants = make_binary_vectorscalar_variants(
            op_test_def, vector_position="lhs"
        )
        if op_test_def.kind.uniform_input_types:
            if op_test_def.kind.commutative:
                for vec_variant in list(vec_variants):
                    # vector_rhs-none_commutative does not currently work because of the way we do nullability!
                    # We have op(None, [vec]) in this case, and we want a vector of nulls, but nullability
                    # returns None immediately at a very early stage.
                    # TODO: fix!
                    if vec_variant.scalar != None:
                        variants.append(
                            vec_variant.variant("commutative", vec_first=False)
                        )
            else:
                vec_variants.extend(
                    make_binary_vectorscalar_variants(
                        op_test_def, vector_position="rhs"
                    )
                )
        variants.extend(vec_variants)

    return variants


def make_all_variants() -> list[tuple[str, OpTestCase]]:
    variants: list[OpTestCase] = []
    for op_test_def in OP_TEST_SPECS:
        variants.extend(make_op_variants(op_test_def))
    return [("_".join(v.name), v) for v in variants]


VARIANTS = dict(make_all_variants())

SKIPS = set(
    [
        # test doesn't produce correct expected output
        "joinAll_case1_vecdim1",
        # op implementation produces incorrect output
        "joinAll_case0_arg0-tag_vecdim1",
        "joinAll_case1_arg0-tag_vecdim1",
    ]
)


@pytest.mark.parametrize("name", [name for name in VARIANTS.keys()])
def test_all_ops(name: str):
    if name in SKIPS:
        return
    test = VARIANTS[name]
    test.check()
