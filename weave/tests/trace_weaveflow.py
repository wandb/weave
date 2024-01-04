import weave
from weave import weaveflow

# This is just an experiment script, it is not a real test for now because we dont
# have a unit test harness set up that supports what this needs to run successfully.
# To get it working we need a fixture for weave.init().
# TODO: convert this into a real test.


weave.init("weave_memo_5")


@weave.type()
class CustomObject:
    a: int


@weave.op()
def custom_object_adder(a: CustomObject, b: CustomObject) -> CustomObject:
    print("hello")
    return CustomObject(a.a + b.a)


if __name__ == "__main__":
    five = custom_object_adder(CustomObject(2), CustomObject(5))
    print(five)
    fiv3 = custom_object_adder(CustomObject(2), CustomObject(5))
    print(fiv3)
