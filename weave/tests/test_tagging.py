import pytest
import weave
from ..language_features.tagging import make_tag_getter_op, tagged_value_type, tag_store
from .. import weave_types as types


def test_tagged_value():
    tv = tagged_value_type.TaggedValueType(
        types.TypedDict({"a": types.Number()}), types.String()
    )
    assert tv.value == types.String()
    assert tv.tag == types.TypedDict({"a": types.Number()})


def test_tagged_types():
    @weave.type()
    class TestNumber:
        inner: int

    @weave.op()
    def add_tester(a: TestNumber, b: TestNumber) -> TestNumber:
        return TestNumber(a.inner + b.inner)

    @weave.op()
    def add_tester_2(d: TestNumber, e: TestNumber) -> TestNumber:
        return TestNumber(d.inner + e.inner)

    get_a_tag = make_tag_getter_op.make_tag_getter_op("a", TestNumber.WeaveType())
    get_d_tag = make_tag_getter_op.make_tag_getter_op("d", TestNumber.WeaveType())

    # 1: Assert that that the tester works
    three = add_tester(TestNumber(1), TestNumber(2))
    assert weave.use(three).inner == 3

    # 2: Assert that we can get a tag
    assert weave.use(get_a_tag(three)).inner == 1

    # 3: Assert that we can use tagged values instead of raw values
    seven = add_tester(TestNumber(3), TestNumber(4))
    ten = add_tester_2(three, seven)
    assert ten.type == tt({"a": 1, "d": 3}, TestNumber.WeaveType())
    assert (
        isinstance(ten.type, tagged_value_type.TaggedValueType)
        and isinstance(
            ten.type.tag.property_types["d"], tagged_value_type.TaggedValueType
        )
        and isinstance(ten.type.tag.property_types["d"].value, TestNumber.WeaveType)
    )
    assert weave.use(ten).inner == 10

    # 4: Show that tags flow through
    assert weave.use(get_a_tag(ten)).inner == 1
    assert weave.use(get_d_tag(ten)).inner == 3

    # 5: Show that saving works:
    ten = weave.save(ten)
    assert weave.use(ten).inner == 10
    assert weave.use(get_a_tag(ten)).inner == 1


def test_index_checkpoint():
    arr = weave.save([1, 2, 3, 4])
    assert weave.use(arr) == [1, 2, 3, 4]
    tagged_arr = arr.createIndexCheckpointTag()
    assert weave.use(tagged_arr) == [1, 2, 3, 4]
    first_item = tagged_arr[0]
    assert weave.use(first_item) == 1
    first_item_index = first_item.indexCheckpoint()
    assert weave.use(first_item_index) == 0
    assert weave.use(tagged_arr[3].indexCheckpoint()) == 3


def tt(tag_dict, value_type):
    return tagged_value_type.TaggedValueType(types.TypedDict(tag_dict), value_type)


### Test Suite v2
@pytest.mark.parametrize(
    "target_type, next_type, is_assignable",
    [
        # empty tags and no tags
        (tt({}, types.Any()), types.Number(), False),
        (tt({}, types.Number()), types.Number(), False),
        (tt({}, types.String()), types.Number(), False),
        # no tags and empty tags
        (types.Any(), tt({}, types.Number()), True),
        (types.Number(), tt({}, types.Number()), True),
        (types.String(), tt({}, types.Number()), False),
        # no tags and some tags
        (types.Any(), tt({"a": types.Number()}, types.Number()), True),
        (types.Number(), tt({"a": types.Number()}, types.Number()), True),
        (types.String(), tt({"a": types.Number()}, types.Number()), False),
        # empty tags and empty tags
        (tt({}, types.Any()), tt({}, types.Number()), True),
        (tt({}, types.Number()), tt({}, types.Number()), True),
        (tt({}, types.String()), tt({}, types.Number()), False),
        # missing Tags
        (tt({"a": types.Number()}, types.Any()), tt({}, types.Number()), False),
        (tt({"a": types.Number()}, types.Number()), tt({}, types.Number()), False),
        (tt({"a": types.Number()}, types.String()), tt({}, types.Number()), False),
        # tag match
        (
            tt({"a": types.Number()}, types.Any()),
            tt({"a": types.Number()}, types.Number()),
            True,
        ),
        (
            tt({"a": types.Number()}, types.Number()),
            tt({"a": types.Number()}, types.Number()),
            True,
        ),
        (
            tt({"a": types.Number()}, types.String()),
            tt({"a": types.Number()}, types.Number()),
            False,
        ),
        # tag mismatch
        (
            tt({"a": types.Number()}, types.Any()),
            tt({"b": types.Number()}, types.Number()),
            False,
        ),
        (
            tt({"a": types.Number()}, types.Number()),
            tt({"b": types.Number()}, types.Number()),
            False,
        ),
        (
            tt({"a": types.Number()}, types.String()),
            tt({"b": types.Number()}, types.Number()),
            False,
        ),
        # tag superset
        (
            tt({"a": types.Number()}, types.Any()),
            tt({"a": types.Number(), "b": types.String()}, types.Number()),
            True,
        ),
        (
            tt({"a": types.Number()}, types.Number()),
            tt({"a": types.Number(), "b": types.String()}, types.Number()),
            True,
        ),
        (
            tt({"a": types.Number()}, types.String()),
            tt({"a": types.Number(), "b": types.String()}, types.Number()),
            False,
        ),
    ],
)
def test_tagged_value_assignment(target_type, next_type, is_assignable):
    assert target_type.assign_type(next_type) == is_assignable


def test_tag_lookups():
    @weave.type()
    class TestObj:
        inner: int

    # Test Simple Lookup
    obj_1 = TestObj(1)
    tag_store.add_tags(obj_1, {"a": 1})
    assert tag_store.find_tag(obj_1, "a") == 1

    obj_2 = TestObj(1)
    tag_store.add_tags(obj_2, {"a": 2, "b": 2})
    assert tag_store.find_tag(obj_2, "a") == 2
    assert tag_store.find_tag(obj_2, "b") == 2

    # Test Ancestor Lookup with name overlap
    obj_3 = TestObj(1)
    tag_store.add_tags(obj_3, {"nest": obj_2, "b": 3})
    assert tag_store.find_tag(obj_3, "a") == 2
    assert tag_store.find_tag(tag_store.find_tag(obj_3, "nest"), "b") == 2
    assert tag_store.find_tag(obj_3, "b") == 3
