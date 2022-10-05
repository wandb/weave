import weave
from .. import graph


def test_tagged_types():
    @weave.op(
        # output_type=weave.types.TaggedType(weave.types.TypedDict({
        #     "a": weave.types.Int(),
        # }), weave.types.Int()),
    )
    def add_tester(a: int, b: int):
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
        return a._tag["tim"]

    # assert(weave.use(graph.OutputNode(weave.types.Number(),"typedDict-pick",{
    #     "self": incorrect_return_type(1), "key": graph.ConstNode(weave.types.String(), "a")})) == 1)

    # 1: Assert that that they tester works
    assert weave.use(add_tester(1, 2)) == 3

    # 2: Assert that we can get a tag
    one = weave.types.TaggedValue.create(1, {"tim": 42})
    assert weave.use(get_tim_tag(one)) == 42

    # 3: Assert that we can use tagged values instread of raw values
    two = weave.types.TaggedValue.create(2, {"sweeney": "hello world"})
    addition = add_tester(one, two)
    assert weave.use(addition) == 3

    # 4: Show that tags flow through
    assert weave.use(get_tim_tag(addition)) == 42

    # 5: Show that saving works:
    addition = weave.save(addition)
    assert weave.use(get_tim_tag(addition)) == 42
