from datetime import datetime, timedelta, timezone

import weave
from weave.trace.weave_client import WeaveClient, get_ref


def make_datetime(
    *,
    year: int = 2024,
    month: int = 1,
    day: int = 1,
    hour: int = 12,
    minute: int = 0,
    second: int = 0,
    microsecond: int = 0,
    tzinfo: timezone | None = None,
) -> datetime:
    """Create a datetime, defaulting to noon 2024 (no timezone)."""
    return datetime(year, month, day, hour, minute, second, microsecond, tzinfo=tzinfo)


EST = timezone(timedelta(hours=-5), "EST")


class DateTimeWrapper(weave.Object):
    dt: datetime


@weave.op
def datetime_as_solo_output(publish_first: bool, dt: datetime) -> datetime:
    if publish_first:
        weave.publish(dt)
    return dt


@weave.op
def datetime_as_input_and_output_part(in_dt: datetime) -> dict:
    return {"out_dt": in_dt}


def test_basic_datetime_serialization(client: WeaveClient):
    # Test with timezone-aware datetime
    dt = make_datetime(tzinfo=EST)
    ref = weave.publish(dt)
    gotten_dt = ref.get()
    # When a timezone-aware datetime is published, it's converted to UTC
    utc_dt = dt.astimezone(timezone.utc)
    assert gotten_dt == utc_dt
    assert gotten_dt.tzinfo == timezone.utc

    # Test with naive datetime (should be converted to UTC)
    naive_dt = make_datetime()
    ref = weave.publish(naive_dt)
    gotten_dt = ref.get()
    utc_dt = naive_dt.replace(tzinfo=timezone.utc)
    assert gotten_dt == utc_dt
    assert gotten_dt.tzinfo == timezone.utc


def test_datetime_as_attribute(client: WeaveClient) -> None:
    dt = make_datetime(tzinfo=EST)
    dt_wrapper = DateTimeWrapper(dt=dt)
    assert dt_wrapper.dt == dt

    weave.publish(dt_wrapper)
    ref = get_ref(dt_wrapper)
    assert ref is not None

    gotten_dt_wrapper = weave.ref(ref.uri()).get()
    # When a timezone-aware datetime is published, it's converted to UTC
    utc_dt = dt.astimezone(timezone.utc)
    assert gotten_dt_wrapper.dt == utc_dt
    assert gotten_dt_wrapper.dt.tzinfo == timezone.utc


def test_datetime_as_call_io(client: WeaveClient) -> None:
    dt = make_datetime(tzinfo=EST)

    non_published_dt = datetime_as_solo_output(publish_first=False, dt=dt)
    dt_dict = datetime_as_input_and_output_part(non_published_dt)

    # When passing through ops, datetimes are converted to UTC
    utc_dt = dt.astimezone(timezone.utc)
    assert dt_dict["out_dt"] == utc_dt
    assert dt_dict["out_dt"].tzinfo == timezone.utc

    datetime_as_solo_output_call = datetime_as_solo_output.calls()[0]
    datetime_as_input_and_output_part_call = datetime_as_input_and_output_part.calls()[
        0
    ]

    assert datetime_as_solo_output_call.output == utc_dt
    assert datetime_as_input_and_output_part_call.inputs["in_dt"] == utc_dt
    assert datetime_as_input_and_output_part_call.output["out_dt"] == utc_dt


def test_datetime_as_call_io_refs(client: WeaveClient) -> None:
    dt = make_datetime(tzinfo=EST)

    non_published_dt = datetime_as_solo_output(publish_first=True, dt=dt)
    dt_dict = datetime_as_input_and_output_part(non_published_dt)

    # When passing through ops, datetimes are converted to UTC
    utc_dt = dt.astimezone(timezone.utc)
    assert dt_dict["out_dt"] == utc_dt
    assert dt_dict["out_dt"].tzinfo == timezone.utc

    datetime_as_solo_output_call = datetime_as_solo_output.calls()[0]
    datetime_as_input_and_output_part_call = datetime_as_input_and_output_part.calls()[
        0
    ]

    assert datetime_as_solo_output_call.output == utc_dt
    assert datetime_as_input_and_output_part_call.inputs["in_dt"] == utc_dt
    assert datetime_as_input_and_output_part_call.output["out_dt"] == utc_dt


def test_datetime_as_dataset_cells(client: WeaveClient):
    # Test with both timezone-aware and naive datetimes
    dts = [
        make_datetime(tzinfo=EST),
        make_datetime(),  # Naive (no timezone)
    ]

    rows = [{"dt": dt} for dt in dts]
    dataset = weave.Dataset(rows=rows)
    ref = weave.publish(dataset)

    dataset = ref.get()
    for gotten_row, dt in zip(dataset, dts):
        assert isinstance(gotten_row["dt"], datetime)
        if dt.tzinfo is not None:
            # When a timezone-aware datetime is published, it's converted to UTC
            utc_dt = dt.astimezone(timezone.utc)
            assert gotten_row["dt"] == utc_dt
            assert gotten_row["dt"].tzinfo == timezone.utc
        else:
            # When a naive datetime is published, it's converted to UTC
            utc_dt = dt.replace(tzinfo=timezone.utc)
            assert gotten_row["dt"] == utc_dt
            assert gotten_row["dt"].tzinfo == timezone.utc
