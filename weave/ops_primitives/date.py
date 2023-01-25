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
    name="dates-equal",
    input_type={
        "lhs": types.union(types.Timestamp(), types.LegacyDate()),
        "rhs": types.union(types.Timestamp(), types.LegacyDate()),
    },
    output_type=types.Boolean(),
)
def dates_equal(lhs, rhs):
    return lhs == rhs
