import datetime

import pytest

from weave.trace.box import box, unbox


@pytest.mark.parametrize(
    "value",
    [
        1,
        1.0,
        "hello",
        datetime.datetime(2024, 1, 1, 12, 34, tzinfo=datetime.timezone.utc),
        datetime.timedelta(seconds=1),
    ],
)
def test_unbox_round_trips_box(value):
    """Unbox must reproduce what box stored, as a plain type.

    Not what box was *handed*: box normalizes a datetime to UTC, so a naive input
    comes back aware and the round trip is only lossless from box's output on.
    """
    unboxed = unbox(box(value))

    # Equality alone would pass on a boxed value: the subclasses compare equal.
    assert type(unboxed) is type(value)
    assert unboxed == value
