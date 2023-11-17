import typing
import dateutil
import dateutil.parser
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
    name="datetime-addms",
    input_type={
        "lhs": types.UnionType(types.Timestamp(), types.Number()),
        "rhs": lambda input_types: types.optional(
            types.Timestamp()
            if types.Number().assign_type(input_types["lhs"])
            else types.Number()
        ),
    },
    output_type=types.optional(types.Timestamp()),
)
def datetime_add(lhs, rhs):
    if rhs == None:
        return None
    return lhs + datetime.timedelta(milliseconds=rhs)


AUTO_FORMAT_UNITS_AND_NUM_MS = (
    ("years", 365 * 24 * 60 * 60 * 1000),
    ("months", 30 * 24 * 60 * 60 * 1000),  # Approximating a month as 30 days
    ("days", 24 * 60 * 60 * 1000),
    ("hours", 60 * 60 * 1000),
    ("minutes", 60 * 1000),
    ("seconds", 1000),
    ("milliseconds", 1),
)


@op(
    name="timestamp-relativeStringAutoFormat",
    input_type={
        "timestamp1": types.Timestamp(),
        "timestamp2": types.optional(types.Timestamp()),
    },
    output_type=types.optional(types.String()),
)
def auto_format_relative_string(timestamp1, timestamp2):
    if timestamp2 == None:
        return None

    delta: datetime.timedelta = timestamp1 - timestamp2
    diff_ms = delta.total_seconds() * 1000

    for unit, unit_ms in AUTO_FORMAT_UNITS_AND_NUM_MS:
        if abs(diff_ms) >= unit_ms:
            rounding_unit = 1 if unit == "years" or unit == "months" else 0
            diff = round(diff_ms / unit_ms, rounding_unit)

            if int(diff) == diff:
                diff = int(diff)

            if abs(diff) == 1:
                unit = unit[:-1]

            return f"{diff} {unit}"

    return "less than 1 ms"


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
    return int(date.timestamp()) * 1000


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
def floor(date, multiple_s: float):
    seconds = (date.replace(tzinfo=None) - date.min).seconds
    rounding = (seconds // multiple_s) * multiple_s
    return date + datetime.timedelta(0, rounding - seconds, -date.microsecond)


@op(
    name="date-ceil",
    input_type={"date": types.union(types.Timestamp(), types.LegacyDate())},
    output_type=types.Timestamp(),
)
def ceil(date, multiple_s: float):
    seconds = (date.replace(tzinfo=None) - date.min).seconds
    rounding = (seconds // multiple_s) * multiple_s
    return date + datetime.timedelta(
        0, rounding - seconds + multiple_s, -date.microsecond
    )


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


# Flexible date parsing, but not implemented in weaveJS so a round-trip
# is incurred to use it.
@op(render_info={"type": "function"})
def date_parse(dt_s: str) -> typing.Optional[datetime.datetime]:
    try:
        return dateutil.parser.parse(dt_s)  # type: ignore
    except dateutil.parser.ParserError:
        return None


@op(render_info={"type": "function"})
def days(days: int) -> datetime.timedelta:
    return datetime.timedelta(days=days)


# This is used as a construct, ie, it is specific and not very flexible.
# It only handles ISO formatted strings. This way we can make it match
# the js implementation exactly.
# date_parse above can be used for flexible parsing.
@op(name="timestamp", render_info={"type": "function"})
def timestamp(timestampISO: str) -> typing.Optional[datetime.datetime]:
    try:
        return datetime.datetime.fromisoformat(timestampISO)
    except ValueError:
        # TODO: Figure out why a non-iso format is getting emitted from the new DatePicker.
        # This is a hack to get around that.
        try:
            return dateutil.parser.parse(timestampISO)
        except dateutil.parser.ParserError:
            return None
