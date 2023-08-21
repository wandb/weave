import typing
import datetime
from ..ops_primitives import date
import pytest

import weave


def assert_date_string(
    diff: typing.Union[float, int],
    unit: str,
    suffix: typing.Literal["ago", "from now"],
    actual: str,
):
    if diff == 1:
        unit = unit[:-1]

    diff = round(diff, 2)
    if int(diff) == diff:
        diff = int(diff)

    expected = f"{diff} {unit} {suffix}"
    assert actual == expected


@pytest.mark.parametrize(
    "multiplier,unit,num_ms",
    [
        (m, u, nms)
        for m in [1, 1.5, 3, 5.3432, 8.00000000007]
        for u, nms in date.AUTO_FORMAT_UNITS_AND_NUM_MS
    ],
)
def test_relative_string_autoformat(multiplier, unit, num_ms):
    ts1 = datetime.datetime.now()
    ts2 = ts1 + datetime.timedelta(milliseconds=num_ms * multiplier)

    from_now_result = weave.use(date.auto_format_relative_string(ts1, ts2))
    ago_result = weave.use(date.auto_format_relative_string(ts2, ts1))

    assert_date_string(multiplier, unit, "from now", from_now_result)
    assert_date_string(multiplier, unit, "ago", ago_result)
