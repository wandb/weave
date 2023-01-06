import typing
import datetime
import math
from ..api import op, mutation, weave_class
from .. import weave_types as types


@weave_class(weave_type=types.Number)
class Number(object):
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
        input_type={"lhs": types.Number(), "rhs": types.Number()},
        output_type=types.Number(),
    )
    def __floordiv__(lhs, rhs):
        return lhs // rhs

    @op(
        name="number-modulo",
        input_type={"lhs": types.Number(), "rhs": types.Number()},
        output_type=types.Number(),
    )
    def __mod__(lhs, rhs):
        return lhs % rhs

    @op(
        name="number-powBinary",
        input_type={"lhs": types.Number(), "rhs": types.Number()},
        output_type=types.Number(),
    )
    def __pow__(lhs, rhs):
        return lhs**rhs

    @op(
        name="number-equal",
        input_type={
            "lhs": types.optional(types.Number()),
            "rhs": types.optional(types.Number()),
        },
        output_type=types.optional(types.Boolean()),
    )
    def __eq__(lhs, rhs):
        return lhs == rhs

    @op(
        name="number-notEqual",
        input_type={
            "lhs": types.optional(types.Number()),
            "rhs": types.optional(types.Number()),
        },
        output_type=types.optional(types.Boolean()),
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
        name="number-negate",
        input_type={"val": types.Number()},
        output_type=types.Number(),
    )
    def __neg__(val):
        return val * -1

    @op(
        name="number-round",
        input_type={"val": types.Number()},
        output_type=types.Number(),
    )
    def __round__(val):
        return round(val)

    @op(
        name="number-floor",
        input_type={"number": types.Number()},
        output_type=types.Number(),
    )
    def floor(number):
        return math.floor(number)

    @op(
        name="number-ceil",
        input_type={"number": types.Number()},
        output_type=types.Number(),
    )
    def ceil(number):
        return math.ceil(number)

    @op(
        name="number-pow",
        input_type={"lhs": types.Number(), "rhs": types.Number()},
        output_type=types.Number(),
    )
    def pow(lhs, rhs):
        return lhs**rhs

    @op(
        name="number-cos",
        input_type={"n": types.Number()},
        output_type=types.Number(),
    )
    def cos(n):
        return math.cos(n)

    @op(
        name="number-sin",
        input_type={"n": types.Number()},
        output_type=types.Number(),
    )
    def sin(n):
        return math.sin(n)

    @op(
        name="number-toTimestamp",
        input_type={"val": types.Number()},
        output_type=types.Datetime(),
    )
    def to_timestamp(val):
        # TODO: We may need to handle more conversion points similar to Weave0
        timestamp_second_upper_bound = 60 * 60 * 24 * 365 * 1000
        # first 1000 years
        if val > timestamp_second_upper_bound:
            val = val / 1000
        return datetime.datetime.fromtimestamp(val, tz=datetime.timezone.utc)

    @op(
        name="number-toString",
        input_type={"val": types.Number()},
        output_type=types.String(),
    )
    def to_string(val):
        return str(val)


def numbers_ops_output_type(input_types: dict[str, types.Type]) -> types.Type:
    arr_type = typing.cast(types.List, input_types["numbers"])
    if types.List(types.NoneType()).assign_type(arr_type):
        return types.NoneType()
    elif types.List(types.Number()).assign_type(arr_type):
        return arr_type.object_type
    else:
        return types.optional(arr_type.object_type)


def avg_output_type(input_types: dict[str, types.Type]) -> types.Type:
    arr_type = typing.cast(types.List, input_types["numbers"])
    if types.List(types.NoneType()).assign_type(arr_type):
        return types.NoneType()
    elif types.List(types.Number()).assign_type(arr_type):
        return types.Number()
    else:
        return types.optional(types.Number())


@op(
    name="numbers-sum",
    input_type={"numbers": types.List(types.optional(types.Number()))},
    output_type=numbers_ops_output_type,
)
def numbers_sum(numbers):
    numbers = [n for n in numbers if n != None]
    return sum(numbers) if len(numbers) > 0 else None


@op(
    name="numbers-avg",
    input_type={"numbers": types.List(types.optional(types.Number()))},
    output_type=avg_output_type,
)
def numbers_avg(numbers):
    numbers = [n for n in numbers if n != None]
    return sum(numbers) / len(numbers) if len(numbers) > 0 else None


@op(
    name="numbers-min",
    input_type={"numbers": types.List(types.optional(types.Number()))},
    output_type=numbers_ops_output_type,
)
def numbers_min(numbers):
    numbers = [n for n in numbers if n != None]
    return min(numbers) if len(numbers) > 0 else None


@op(
    name="numbers-max",
    input_type={"numbers": types.List(types.optional(types.Number()))},
    output_type=numbers_ops_output_type,
)
def numbers_max(numbers):
    numbers = [n for n in numbers if n != None]
    return max(numbers) if len(numbers) > 0 else None


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
