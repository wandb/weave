import weave
from .. import graph


def test_tagged_types():
    @weave.op(
        # output_type=weave.types.TaggedType(weave.types.TypedDict({
        #     "a": weave.types.Int(),
        # }), weave.types.Int()),
    )
    def add_tester(a: int, b: int) -> int:
        return a + b

    # @weave.op()
    # def incorrect_return_type(a: int) -> int:
    #     return {"a": a}

    @weave.op(
        input_type={
            "a": weave.types.TaggedType(
                weave.types.TypedDict({"tim": weave.types.Int()}), weave.types.Any()
            ),
        },
    )
    def get_tim_tag(a) -> int:
        return a.tag["tim"]

    # assert(weave.use(graph.OutputNode(weave.types.Number(),"typedDict-pick",{
    #     "self": incorrect_return_type(1), "key": graph.ConstNode(weave.types.String(), "a")})) == 1)

    # 1: Assert that that they tester works
    assert weave.use(add_tester(1, 2)) == 3

    # 2: Assert that we can get a tag
    one = weave.types.TaggedValue({"tim": 42}, 1)
    assert weave.use(get_tim_tag(one)) == 42

    # 3: Assert that we can use tagged values instread of raw values
    two = weave.types.TaggedValue({"sweeney": "hello world"}, 2)
    addition = add_tester(one, two)
    assert weave.use(addition) == 3

    # 4: Show that tags flow through
    assert weave.use(get_tim_tag(addition)) == 42

    # 5: Show that saving works:
    addition = weave.save(addition)
    assert weave.use(get_tim_tag(addition)) == 42


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
