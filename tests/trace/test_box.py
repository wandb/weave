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
    """Unbox must give back the value box was handed, tzinfo included."""
    assert unbox(box(value)) == value
