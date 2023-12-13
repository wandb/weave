import weave
from weave import weaveflow


weave.init("weave_memo_2")


@weave.op()
def my_add(a: int, b: int) -> int:
    print("hello")
    return a + b


if __name__ == "__main__":
    five = my_add(2, 5)
    print(five)
    fiv3 = my_add(2, 5)
    print(fiv3)
