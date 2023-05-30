import dateutil
from ..api import op, type
from .. import weave_types as types
import datetime


@op(
    name="datetime-sub",
    input_type={
        "lhs": types.Timestamp(),
        "rhs": types.optional(types.Timestamp()),
    },
    output_type=types.optional(types.TimeDelta()),
)
def datetime_sub(lhs, rhs):
    if rhs == None:
        return None
    return lhs - rhs


@op(
    name="datetimetd-sub",
    input_type={
        "lhs": types.Timestamp(),
        "rhs": types.optional(types.TimeDelta()),
    },
    output_type=types.optional(types.Timestamp()),
)
def datetimetd_sub(lhs, rhs):
    if rhs == None:
        return None
    return lhs - rhs


@op(
    name="datetime-add",
    input_type={
        "lhs": types.UnionType(types.Timestamp(), types.TimeDelta()),
        "rhs": lambda input_types: types.optional(
            types.Timestamp()
            if types.TimeDelta().assign_type(input_types["lhs"])
            else types.TimeDelta()
        ),
    },
    output_type=types.optional(types.Timestamp()),
)
def datetime_add(lhs, rhs):
    if rhs == None:
        return None
    return lhs + rhs


@op(
    name="timedelta-mult",
    input_type={
        "lhs": types.UnionType(types.Number(), types.TimeDelta()),
        "rhs": lambda input_types: types.optional(
            types.TimeDelta()
            if types.Number().assign_type(input_types["lhs"])
            else types.Number()
        ),
    },
    output_type=types.optional(types.TimeDelta()),
)
def timedelta_mult(lhs, rhs):
    if rhs == None:
        return None
    return lhs * rhs


@op(
    name="timedelta-div",
    input_type={"lhs": types.TimeDelta(), "rhs": types.optional(types.Number())},
    output_type=types.optional(types.TimeDelta()),
)
def timedelta_div(lhs, rhs):
    if rhs == None:
        return None
    return lhs / rhs


@op(
    name="datetime-__le__",
    input_type={
        "lhs": types.optional(types.Timestamp()),
        "rhs": types.optional(types.Timestamp()),
    },
    output_type=types.Boolean(),
)
def datetime_le(lhs, rhs):
    if rhs == None:
        return None
    return lhs <= rhs


@op(
    name="datetime-__lt__",
    input_type={
        "lhs": types.optional(types.Timestamp()),
        "rhs": types.optional(types.Timestamp()),
    },
    output_type=types.Boolean(),
)
def datetime_lt(lhs, rhs):
    if rhs == None:
        return None
    return lhs < rhs


@op(
    name="datetime-__ge__",
    input_type={
        "lhs": types.optional(types.Timestamp()),
        "rhs": types.optional(types.Timestamp()),
    },
    output_type=types.Boolean(),
)
def datetime_ge(lhs, rhs):
    if rhs == None:
        return None
    return lhs >= rhs


@op(
    name="datetime-__gt__",
    input_type={
        "lhs": types.optional(types.Timestamp()),
        "rhs": types.optional(types.Timestamp()),
    },
    output_type=types.Boolean(),
)
def datetime_gt(lhs, rhs):
    if rhs == None:
        return None
    return lhs > rhs


@op(
    name="timedelta-totalSeconds",
    input_type={"td": types.TimeDelta()},
    output_type=types.Number(),
)
def timedelta_total_seconds(td):
    return td.total_seconds()


@op(
    name="date-toNumber",
    input_type={"date": types.union(types.Timestamp(), types.LegacyDate())},
    output_type=types.Number(),
)
def to_number(date):
    return int(date.timestamp())


@op(
    name="date-fromNumber",
    input_type={"number": types.Number()},
    output_type=types.Timestamp(),
)
def from_number(number):
    return datetime.datetime.fromtimestamp(number)


@op(
    name="date-floor",
    input_type={"date": types.union(types.Timestamp(), types.LegacyDate())},
    output_type=types.Timestamp(),
)
def floor(date, multiple_ms: int):
    raise NotImplementedError("floor not implemented")


@op(
    name="date-ceil",
    input_type={"date": types.union(types.Timestamp(), types.LegacyDate())},
    output_type=types.Timestamp(),
)
def ceil(date, multiple_ms: int):
    raise NotImplementedError("ceil not implemented")


@op(
    name="date_round-month",
    input_type={"date": types.union(types.Timestamp(), types.LegacyDate())},
    output_type=types.Timestamp(),
)
def round_month(date):
    return datetime.datetime(date.year, date.month, 1, 0, 0, 0, 0, date.tzinfo)


@op(
    name="date_round-week",
    input_type={"date": types.union(types.Timestamp(), types.LegacyDate())},
    output_type=types.Timestamp(),
)
def round_week(date):
    curr_weekday = date.weekday()  # MON = 0, SUN = 6
    prev_sunday_offset = (
        curr_weekday + 1
    ) % 7  # MON = 0, SUN = 6 -> SUN = 0 .. SAT = 6
    new_date = datetime.datetime(
        date.year, date.month, date.day, 0, 0, 0, 0, date.tzinfo
    )
    new_date -= datetime.timedelta(days=prev_sunday_offset)
    return new_date


@op(
    name="dates-equal",
    input_type={
        "lhs": types.union(types.Timestamp(), types.LegacyDate()),
        "rhs": types.union(types.Timestamp(), types.LegacyDate()),
    },
    output_type=types.Boolean(),
)
def dates_equal(lhs, rhs):
    return lhs == rhs


@op(
    name="timestamp-min",
    input_type={"values": types.List(types.optional(types.Timestamp()))},
    output_type=types.optional(types.Timestamp()),
)
def timestamp_min(values):
    values = [v for v in values if v != None]
    return min(values) if len(values) > 0 else None


@op(
    name="timestamp-max",
    input_type={"values": types.List(types.optional(types.Timestamp()))},
    output_type=types.optional(types.Timestamp()),
)
def timestamp_max(values):
    values = [v for v in values if v != None]
    return max(values) if len(values) > 0 else None


@op(render_info={"type": "function"})
def date_parse(dt_s: str) -> datetime.datetime:
    return dateutil.parser.parse(dt_s)  # type: ignore


@op(render_info={"type": "function"})
def days(days: int) -> datetime.timedelta:
    return datetime.timedelta(days=days)
