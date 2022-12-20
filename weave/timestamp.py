import datetime

# all operations on datetime objects should be tz aware and in utc. If a user
# provides a non-tz aware datetime, we assume their intention is to use the
# system timezone and convert to utc.
def tz_aware_dt(dt: datetime.datetime) -> datetime.datetime:
    if dt.tzinfo is None:
        dt = dt.astimezone()  # uses system timezone
    return dt.astimezone(datetime.timezone.utc)
