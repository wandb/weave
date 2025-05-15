import asyncio
import weave

weave.init("test")

@weave.op()
def add(a: int, b: int) -> int:
    return a + b

@weave.op()
def score(a: int, b: int, output:int) -> int:
    return a + b == output



eval = weave.Evaluation(
    dataset=[{"a": 1, "b": 2}, {"a": 3, "b": 4}],
    scorers=[score],
)

res = asyncio.run(eval.evaluate(add))

