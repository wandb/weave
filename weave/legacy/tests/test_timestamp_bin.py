from datetime import datetime, timedelta, timezone

import pytest

import weave


def test_timestamp_bins_fixed():
    bin_fn = weave.legacy.weave.ops.timestamp_bins_fixed(60)

    ts = datetime(2020, 1, 1, 8, 30, 1)
    called = bin_fn(ts)

    res = weave.use(called)
    assert res["start"] == datetime(2020, 1, 1, 8, 30, 0)
    assert res["stop"] == datetime(2020, 1, 1, 8, 31, 0)


def test_timestamp_bins_nice():
    start_ts = datetime(2020, 1, 1, 8, 30, 1)
    stop_ts = datetime(2020, 1, 1, 12, 30, 0)
    bin_fn = weave.legacy.weave.ops.timestamp_bins_nice([start_ts, stop_ts], 100)

    ts = datetime(2020, 1, 1, 8, 45, 13)
    called = bin_fn(ts)

    res = weave.use(called)
    assert res["start"] == datetime(2020, 1, 1, 8, 45, 0)
    assert res["stop"] == datetime(2020, 1, 1, 8, 46, 0)


def test_timestamp_bin():
    start_ts = datetime(2020, 1, 1, 8, 30, 1)
    stop_ts = datetime(2020, 1, 1, 12, 30, 0)
    bin_fn = weave.legacy.weave.ops.timestamp_bins_nice([start_ts, stop_ts], 100)

    ts = datetime(2020, 1, 1, 8, 45, 13)
    ts_node = weave.save(ts)

    res2 = weave.use(ts_node.bin(bin_fn))
    assert res2["start"] == datetime(2020, 1, 1, 8, 45, 0)
    assert res2["stop"] == datetime(2020, 1, 1, 8, 46, 0)


def test_timestamp_bin_vector():
    start_ts = datetime(2020, 1, 1, 8, 30, 1)
    stop_ts = datetime(2020, 1, 1, 12, 30, 0)
    bin_fn = weave.legacy.weave.ops.timestamp_bins_nice([start_ts, stop_ts], 100)

    ts = datetime(2020, 1, 1, 8, 45, 13, tzinfo=timezone.utc)
    ts_node = weave.legacy.weave.ops.to_weave_arrow([ts, ts + timedelta(seconds=90)])

    # This does not vectorize because mapped ops don't automatically
    # vectorize!
    bin_called = ts_node.bin(bin_fn)
    res = weave.use(bin_called)
    assert res[0]["start"] == datetime(2020, 1, 1, 8, 45, 0, tzinfo=timezone.utc)
    assert res[0]["stop"] == datetime(2020, 1, 1, 8, 46, 0, tzinfo=timezone.utc)
    assert res[1]["start"] == datetime(2020, 1, 1, 8, 46, 0, tzinfo=timezone.utc)
    assert res[1]["stop"] == datetime(2020, 1, 1, 8, 47, 0, tzinfo=timezone.utc)

    mapped_bin_called = ts_node.map(lambda x: x.bin(bin_fn))
    res2 = weave.use(mapped_bin_called)
    assert res2[0]["start"] == datetime(2020, 1, 1, 8, 45, 0, tzinfo=timezone.utc)
    assert res2[0]["stop"] == datetime(2020, 1, 1, 8, 46, 0, tzinfo=timezone.utc)
    assert res2[1]["start"] == datetime(2020, 1, 1, 8, 46, 0, tzinfo=timezone.utc)
    assert res2[1]["stop"] == datetime(2020, 1, 1, 8, 47, 0, tzinfo=timezone.utc)
