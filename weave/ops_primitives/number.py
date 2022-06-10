from ..api import op, mutation, weave_class
from .. import weave_types as types


@weave_class(weave_type=types.Number)
class Number(object):
    @op(
        name="number-set",
        input_type={"self": types.Number(), "val": types.Number()},
        output_type=types.Number(),
    )
    @mutation
    def set(self, val):
        return val

    @op(
        name="number-add",
        input_type={"lhs": types.Number(), "rhs": types.Number()},
        output_type=types.Number(),
    )
    def __add__(lhs, rhs):
        if lhs == None or rhs == None:
            return None
        return lhs + rhs

    @op(
        name="number-sub",
        input_type={"lhs": types.Number(), "rhs": types.Number()},
        output_type=types.Number(),
    )
    def __sub__(lhs, rhs):
        return lhs - rhs

    @op(
        name="number-mult",
        input_type={"lhs": types.Number(), "rhs": types.Number()},
        output_type=types.Number(),
    )
    def __mul__(lhs, rhs):
        return lhs * rhs

    @op(
        name="number-div",
        input_type={"lhs": types.Number(), "rhs": types.Number()},
        output_type=types.Number(),
    )
    def __truediv__(lhs, rhs):
        return lhs / rhs

    @op(
        name="number-equal",
        input_type={"lhs": types.Number(), "rhs": types.Number()},
        output_type=types.Boolean(),
    )
    def __eq__(lhs, rhs):
        return lhs == rhs

    @op(
        name="number-notEqual",
        input_type={"lhs": types.Number(), "rhs": types.Number()},
        output_type=types.Boolean(),
    )
    def __ne__(lhs, rhs):
        return lhs != rhs

    @op(
        name="number-less",
        input_type={"lhs": types.Number(), "rhs": types.Number()},
        output_type=types.Boolean(),
    )
    def __lt__(lhs, rhs):
        return lhs < rhs

    @op(
        name="number-greater",
        input_type={"lhs": types.Number(), "rhs": types.Number()},
        output_type=types.Boolean(),
    )
    def __gt__(lhs, rhs):
        return lhs > rhs

    @op(
        name="number-lessEqual",
        input_type={"lhs": types.Number(), "rhs": types.Number()},
        output_type=types.Boolean(),
    )
    def __le__(lhs, rhs):
        return lhs <= rhs

    @op(
        name="number-greaterEqual",
        input_type={"lhs": types.Number(), "rhs": types.Number()},
        output_type=types.Boolean(),
    )
    def __ge__(lhs, rhs):
        return lhs >= rhs


@op(
    name="numbers-avg",
    input_type={"numbers": types.List(types.Number())},
    output_type=types.Number(),
)
def avg(numbers):
    return sum(numbers) / len(numbers)


@op(
    name="numbers-min",
    input_type={"numbers": types.List(types.Number())},
    output_type=types.Number(),
)
def numbers_min(numbers):
    return min(numbers)


@op(
    name="numbers-max",
    input_type={"numbers": types.List(types.Number())},
    output_type=types.Number(),
)
def numbers_max(numbers):
    return max(numbers)


# @weave_class(weave_type=types.Int)
# class Int:
#     @op(
#         name='int.set',
#         input_type={
#             'self': types.Int(),
#             'val': types.Int()
#         },
#         output_type=types.Invalid())
#     def set(self, val):
#         # How would this work?
#         # self would be a Node
#         # self.from_op is a TypedDict.__get__
#         # you can call self.from_op.setter(**self.from_op.inputs, self)
#         print('INT SET', self, val)
#         # ok but the problem is, walking up the op chain, you're not guaranteed
#         # that object identity means this was a valid mutation
#         # so either we need to call sets all the way up
#         #    or pass that information down through the op graph...
#         # or have it actually be present on val
#         # How do we guarantee that the storage we find up the graph from us
#         #    is the one we want to log the mutation to?
#         # Maybe answer?
#         #   It is if there exists a path of setters up the chain?

#         #
#         # So we walk up until we find an op-call for which there is no
#         #   setter.
#         #   The object that was called on is our storage, where we log
#         #       the mutation.

# Why do we need all this crazy, instead of a separate simple
#   object pathing implementation?
# Well, for multi-set (like assign to a table column OR a table row) we
#   need it.
# Though column assign could be logged as assign to each value in the row
#   and therefore still supported. It generates lots of calls to do that.
# But still, it could be that we follow the simple path
#    (dict get, prop get, list index). Each of those has a reversible setter
#    or the user can add their own setters.
# But wait, what about this case?
#    table.col('j')[5].set(19)  # the problem here is that table.col()
#    breaks mutability.
# So we do need a solution that actually propagates the sets all the way back
#    through the chain. (as an immutable update?)

# Issue with the query method:
#    - If the user did the query and then the underlying object changed, we lose
#      track of the object.
#    - So then objects need to track their parents (more memory efficient)
#      Or their IDs, and the client needs this information so it can dispatch
#      updates against actual IDs rather than against queries

# or in the case where we have an object that has setter method that needs
# to update multiple things
# def some_mutation()
#   self.x = 9, self.y = 10
# setting attributes on self just needs to be logged.
