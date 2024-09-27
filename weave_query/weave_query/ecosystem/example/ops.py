# Put your types, ops and panels here.

import weave_query as weave
import weave_query


@weave.op()
def an_example_op(x: int) -> str:
    return "The number is " + str(x)


# TODO: more examples!
