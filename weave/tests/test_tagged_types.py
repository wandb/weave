import weave
from .. import graph


def test_tagged_value():
    assert weave.types.TaggedValue({"a": 1}, 2)._value == 2


def test_tagged_types():
    @weave.op(
        # output_type=weave.types.TaggedType(weave.types.TypedDict({
        #     "a": weave.types.Int(),
        # }), weave.types.Int()),
    )
    def add_tester(a: int, b: int) -> int:
        # import pdb; pdb.set_trace()
        return a + b

    # @weave.op()
    # def incorrect_return_type(a: int) -> int:
    #     return {"a": a}

    @weave.op(
        input_type={
            "a": weave.types.TaggedType(
                weave.types.TypedDict({"a": weave.types.Int()}), weave.types.Any()
            ),
        },
    )
    def get_a_tag(a) -> int:
        return a._tag["a"]

    # assert(weave.use(graph.OutputNode(weave.types.Number(),"typedDict-pick",{
    #     "self": incorrect_return_type(1), "key": graph.ConstNode(weave.types.String(), "a")})) == 1)

    # 1: Assert that that they tester works
    three = add_tester(1, 2)
    assert weave.use(three) == 3

    # 2: Assert that we can get a tag
    assert weave.use(get_a_tag(three)) == 1

    # 3: Assert that we can use tagged values instread of raw values
    seven = add_tester(3, 4)
    ten = add_tester(three, seven)
    assert weave.use(ten) == 10

    # 4: Show that tags flow through
    assert weave.use(get_a_tag(ten)) == 3

    # 5: Show that saving works:
    ten = weave.save(ten)
    assert weave.use(ten) == 10
    # import pdb; pdb.set_trace()
    assert weave.use(get_a_tag(ten)) == 3


def test_tag_adder():
    arr = weave.save([1, 2, 3, 4])
    assert weave.use(arr) == [1, 2, 3, 4]
    tagged_arr = arr.createIndexCheckpointTag()
    assert weave.use(tagged_arr) == [1, 2, 3, 4]
    first_item = tagged_arr[0]
    assert weave.use(first_item) == 1
    first_item_index = first_item.indexCheckpoint()
    assert weave.use(first_item_index) == 0
    assert weave.use(tagged_arr[3].indexCheckpoint()) == 3
