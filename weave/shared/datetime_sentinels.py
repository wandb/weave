"""Datetime defaults shared by stored agent spans and API schemas."""

import datetime

SENTINEL_EPOCH = datetime.datetime(1970, 1, 1, tzinfo=datetime.timezone.utc)
# expire_at uses a far-future sentinel so that ClickHouse's TTL DELETE clause
# (toDateTime(expire_at) DELETE) does not see "no TTL" rows as already expired.
EXPIRE_AT_NEVER = datetime.datetime(2100, 1, 1, tzinfo=datetime.timezone.utc)
