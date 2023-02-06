from ..api import op
from .. import weave_types as types
import datetime


@op(
    name="date-toNumber",
    input_type={"date": types.union(types.Timestamp(), types.LegacyDate())},
    output_type=types.Number(),
)
def to_number(date):
    return int(date.timestamp())


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
