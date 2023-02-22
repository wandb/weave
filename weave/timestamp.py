import datetime
from math import floor
import typing

# Rules for Timestamps in Weave:
# 1. For now, we only support UTC timestamps. This is not a hard requirement and is more a
#    limitation of the current type system. We will have no problem supporting other timezones in the future
# 2. Unless otherwise specified, all timestamps are assumed to be in milliseconds.
#    * The only exception to this rule is if the timestamp is outside of the range of the
#      builtin datetime library. In this case, we will assume the timestamp is in nano or
#      micro seconds since some old sdk versions emitted this resolution
# 3. The resolution should not be finer than milliseconds. This means on disk, we store
#    timestamps as integers (for both AWL and normal lists). Furthermore, at runtime, we
#    use the datetime library which wants seconds for the constructor and produces seconds
#    for the timestamp() method. In these cases we need to be careful and do the proper division
#    or multiplication to get the correct resolution. Helper functions are provided at the bottom
#    of this file to help with this.


# all operations on datetime objects should be tz aware and in utc. If a user
# provides a non-tz aware datetime, we assume their intention is to use the
# system timezone and convert to utc.
def tz_aware_dt(dt: datetime.datetime) -> datetime.datetime:
    if dt.tzinfo is None:
        dt = dt.astimezone()  # uses system timezone
    return dt.astimezone(datetime.timezone.utc)


# These are approximately the min and max timestamps in ms for the builtin
# datetime library. we will make the very conservative assumption that any
# timestamp outside of this range, then the unit is not ms.
PY_DATETIME_MAX_MS = 50000000000000
PY_DATETIME_MIN_MS = -50000000000000


def unitless_int_to_inferred_ms(in_int: typing.Union[float, int]) -> float:
    """
    The SDK will attempt to serialize all timestamps as milliseconds. However, there were older
    versions that would sometimes produce timestamps in seconds or nanoseconds (depending on the
    datetime library used). So, in the vast majority of cases, we can assume this is a ms timestamp,
    but it is possible we are wrong. Moreover, if a user call toTimestamp on a number, in Weave0 we
    try to infer the unit of the number.

    However, in Weave1, we should use this as a learning experience and always use ms timestamps (or have
    the unit specified. If the user wants to use a different unit, they can do a multiply or divide on their
    own data, rather than having us infer it for them.)

    Previously, in Weave0, we had boundaries like:
    const timestampSecondUpperBound = 60 * 60 * 24 * 365 * 1000;
    const timestampMilliSecondUpperBound = timestampSecondUpperBound * 1000;
    const timestampMicroSecondUpperBound = timestampMilliSecondUpperBound * 1000;
    const timestampNanoSecondUpperBound = timestampMicroSecondUpperBound * 1000;

    and made the assumption that values:
        - [-inf, 31536000000] - should be interpreted as seconds
        - [31536000000, 31536000000000] - should be interpreted as milliseconds
        - [31536000000000, 31536000000000000] - should be interpreted as microseconds
        - [31536000000000000, 31536000000000000000] - should be interpreted as nanoseconds

    This has two major problems:
    1. We don't handle negative values correctly in Weave0. (notice the -inf in the first range)
    2. The seconds range introduces a nasty bug (even if we fix the negative values). Let's assume
        that we use the range [-31536000000, 31536000000] for seconds. This means that the timestamp
        range is 970/08/30 16:07:02 to 2969/05/02 17:00:00. However, that same range interpreted as
        milliseconds is 1968/12/31 16:00:00 to 1970/12/31 16:00:00. The result is that if the true unit is
        ms, then dates between those ranges would be incorrectly interpreted as seconds.


    Moving forward, since the SDK is fixed to always send ms, we should just assume that the values are in ms.
    If it is not in ms, then we should correct the data writing code or the user should do a multiply or divide.
    We can add explicit units to the types and conversion ops as well in the future.
    """
    while abs(in_int) > PY_DATETIME_MAX_MS or abs(in_int) < PY_DATETIME_MIN_MS:
        in_int = in_int / 1000
    return in_int


# While the following functions are quite simple, it is useful to have explicitly named
# functions for converting to and from ms timestamps. This makes it more clear in our
# serialization and deserialization code what exactly is happening.
def python_datetime_to_ms(dt: datetime.datetime) -> int:
    return int(dt.timestamp() * 1000)


def ms_to_python_datetime(ms: float) -> datetime.datetime:
    return datetime.datetime.fromtimestamp(floor(ms) / 1000, tz=datetime.timezone.utc)
