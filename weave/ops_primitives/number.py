import typing
import random
import math

from ..api import op, weave_class
from .. import weave_types as types
import numpy as np
from .. import timestamp as weave_timestamp

binary_number_op_input_type = {
    "lhs": types.Number(),
    "rhs": types.optional(types.Number()),
}


def _set_add(lhs, rhs, v, action=None):
    return v - rhs


@weave_class(weave_type=types.Number)
class Number(object):
    @op(
        name="number-add",
        # Just to show that mutations can work in interesting ways.
        setter=_set_add,
        input_type=binary_number_op_input_type,
        output_type=types.Number(),
    )
    def __add__(lhs, rhs):
        if rhs == None or lhs == None:
            return None
        return lhs + rhs

    @op(
        name="number-sub",
        input_type=binary_number_op_input_type,
        output_type=types.Number(),
    )
    def __sub__(lhs, rhs):
        if rhs == None or lhs == None:
            return None
        return lhs - rhs

    @op(
        name="number-mult",
        input_type=binary_number_op_input_type,
        output_type=types.Number(),
    )
    def __mul__(lhs, rhs):
        if rhs == None or lhs == None:
            return None
        return lhs * rhs

    @op(
        name="number-div",
        input_type=binary_number_op_input_type,
        output_type=types.Number(),
    )
    def __truediv__(lhs, rhs):
        rhs = rhs or 0
        if rhs == 0:
            return math.inf
        return lhs / rhs

    @op(
        name="number-floorDiv",
        input_type=binary_number_op_input_type,
        output_type=types.Number(),
    )
    def __floordiv__(lhs, rhs):
        rhs = rhs or 0
        if rhs == 0:
            return math.inf
        return lhs // rhs

    @op(
        name="number-modulo",
        input_type=binary_number_op_input_type,
        output_type=types.Number(),
    )
    def __mod__(lhs, rhs):
        rhs = rhs or 0
        if rhs == 0:
            return 0
        return lhs % rhs

    @op(
        name="number-powBinary",
        input_type=binary_number_op_input_type,
        output_type=types.Number(),
    )
    def __pow__(lhs, rhs):
        rhs = rhs or 0
        return lhs**rhs

    @op(
        name="number-equal",
        input_type={
            **binary_number_op_input_type,
            "lhs": types.optional(types.Number()),
        },
        output_type=types.Boolean(),
    )
    def __eq__(lhs, rhs):
        return lhs == rhs

    @op(
        name="number-notEqual",
        input_type={
            **binary_number_op_input_type,
            "lhs": types.optional(types.Number()),
        },
        output_type=types.Boolean(),
    )
    def __ne__(lhs, rhs):
        return lhs != rhs

    @op(
        name="number-less",
        input_type=binary_number_op_input_type,
        output_type=types.Boolean(),
    )
    def __lt__(lhs, rhs):
        rhs = rhs or 0
        return lhs < rhs

    @op(
        name="number-greater",
        input_type=binary_number_op_input_type,
        output_type=types.Boolean(),
    )
    def __gt__(lhs, rhs):
        rhs = rhs or 0
        return lhs > rhs

    @op(
        name="number-lessEqual",
        input_type=binary_number_op_input_type,
        output_type=types.Boolean(),
    )
    def __le__(lhs, rhs):
        rhs = rhs or 0
        return lhs <= rhs

    @op(
        name="number-greaterEqual",
        input_type=binary_number_op_input_type,
        output_type=types.Boolean(),
    )
    def __ge__(lhs, rhs):
        rhs = rhs or 0
        return lhs >= rhs

    @op(
        name="number-pow",
        input_type=binary_number_op_input_type,
        output_type=types.Number(),
    )
    def pow(lhs, rhs):
        rhs = rhs or 0
        return lhs**rhs

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
        output_type=types.Timestamp(),
    )
    def to_timestamp(val):
        return weave_timestamp.ms_to_python_datetime(
            weave_timestamp.unitless_int_to_inferred_ms(val)
        )

    @op(
        name="number-toString",
        input_type={"val": types.Number()},
        output_type=types.String(),
    )
    def to_string(val):
        return str(val)

    @op(
        name="number-abs",
        input_type={"val": types.Number()},
        output_type=types.Number(),
    )
    def abs(val):
        return abs(val)

    @op(
        name="number-toByteString",
        input_type={"number": types.Number()},
        output_type=types.String(),
    )
    def to_byte_string(number):
        # Convert the number to a byte string.
        # JS version: String(numeral(inputs.in).format('0.00b'))
        unit_maxes = [
            (10**3, "B"),
            (10**6, "KB"),
            (10**9, "MB"),
            (10**12, "GB"),
            (10**15, "TB"),
            (10**18, "PB"),
            (10**21, "EB"),
            (10**24, "ZB"),
            (10**27, "YB"),
        ]
        unit = ""
        number_str = ""
        for unit_ndx, (unit_max, unit_str) in enumerate(unit_maxes):
            if number < unit_max or unit_ndx == len(unit_maxes) - 1:
                unit = unit_str
                if unit_ndx > 0:
                    reduced = number / unit_maxes[unit_ndx - 1][0]
                    number_str = f"{reduced:.2f}"
                else:
                    number_str = f"{number}"
                break

        return f"{number_str}{unit}"

    @op(
        name="number-toFixed",
        input_type={"val": types.Number(), "digits": types.Number()},
        output_type=types.Number(),
    )
    def to_fixed(val, digits):
        return round(val, int(digits))


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


list_of_numbers_input_type = {"numbers": types.List(types.optional(types.Number()))}


@op(
    name="numbers-sum",
    input_type=list_of_numbers_input_type,
    output_type=numbers_ops_output_type,
)
def numbers_sum(numbers):
    numbers = [n for n in numbers if n != None]
    return sum(numbers) if len(numbers) > 0 else None


@op(
    name="numbers-avg",
    input_type=list_of_numbers_input_type,
    output_type=avg_output_type,
)
def numbers_avg(numbers):
    numbers = [n for n in numbers if n != None]
    return sum(numbers) / len(numbers) if len(numbers) > 0 else None


@op(
    name="numbers-min",
    input_type=list_of_numbers_input_type,
    output_type=numbers_ops_output_type,
)
def numbers_min(numbers):
    numbers = [n for n in numbers if n != None]
    return min(numbers) if len(numbers) > 0 else None


@op(
    name="numbers-max",
    input_type=list_of_numbers_input_type,
    output_type=numbers_ops_output_type,
)
def numbers_max(numbers):
    numbers = [n for n in numbers if n != None]
    return max(numbers) if len(numbers) > 0 else None


@op(
    name="numbers-argmax",
    input_type=list_of_numbers_input_type,
    output_type=numbers_ops_output_type,
)
def numbers_argmax(numbers):
    non_null_numbers = [n for n in numbers if n != None]
    if len(non_null_numbers) == 0:
        return None
    return numbers.index(max(non_null_numbers))


@op(
    name="numbers-argmin",
    input_type=list_of_numbers_input_type,
    output_type=numbers_ops_output_type,
)
def numbers_argmin(numbers):
    non_null_numbers = [n for n in numbers if n != None]
    if len(non_null_numbers) == 0:
        return None
    return numbers.index(min(non_null_numbers))


@op(
    name="numbers-stddev",
    input_type=list_of_numbers_input_type,
    output_type=numbers_ops_output_type,
)
def stddev(numbers):
    non_null_numbers = [n for n in numbers if n != None]
    if len(non_null_numbers) == 0:
        return None
    return np.std(non_null_numbers).tolist()


@op(
    name="number-random_normal",
)
def random_normal_single(mean: float, std: float) -> float:
    """
    Generate a single random number drawn from a univariate Gaussian distribution
    with mean `mean` and standard deviation `std`.

    Args:
        mean (float): The mean of the Gaussian distribution.
        std (float): The standard deviation of the Gaussian distribution.

    Returns:
        float: A single float representing the random number generated.
    """
    return random.gauss(mean, std)


@op(
    name="numbers-random_normal",
)
def random_normal(mean: float, std: float, n: int) -> list[float]:
    """
    Generate a list of `n` random numbers drawn from a univariate Gaussian distribution with
    mean `mean` and standard deviation `std`.

    Args:
        mean (float): The mean of the Gaussian distribution.
        std (float): The standard deviation of the Gaussian distribution.
        n (int): The number of random numbers to generate.

    Returns:
        list[float]: A list of `n` floats representing the random numbers generated.
    """
    samples = [random.gauss(mean, std) for _ in range(n)]
    return samples
