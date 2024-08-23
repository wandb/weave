import datetime
import typing

import pytest

import weave
from weave.legacy.weave.ops_primitives import date


def assert_date_string(
    diff: typing.Union[float, int],
    unit: str,
    actual: str,
):
    if abs(diff) == 1:
        unit = unit[:-1]

    round_unit = 1 if unit == "years" or unit == "months" else 0
    diff = round(diff, round_unit)
    if int(diff) == diff:
        diff = int(diff)

    expected = f"{diff} {unit}"
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

    negative_result = weave.use(date.auto_format_relative_string(ts1, ts2))
    positive_result = weave.use(date.auto_format_relative_string(ts2, ts1))

    assert_date_string(multiplier, unit, positive_result)
    assert_date_string(-1 * multiplier, unit, negative_result)


@pytest.mark.parametrize("diff_ms", [0, 0.5, -0.5])
def test_relative_string_autoformat_edge_cases(diff_ms):
    ts1 = datetime.datetime.now()
    ts2 = ts1 + datetime.timedelta(milliseconds=diff_ms)

    result = weave.use(date.auto_format_relative_string(ts1, ts2))
    assert result == "less than 1 ms"
