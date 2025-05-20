import datetime
import os
import time
from unittest import mock

from weave_query import cache, environment


def test_lru_time_window_cache():
    curtime = {"t": datetime.datetime(2020, 1, 1)}

    def now_fn():
        # Time ticks forward 1s at each step
        t = curtime["t"]
        curtime["t"] = t + datetime.timedelta(seconds=1)
        return t

    c = cache.LruTimeWindowCache(datetime.timedelta(seconds=5), now_fn=now_fn)
    c.set("foo", "a")
    c.set("boink", "will_prune")
    c.set("foo", "b")
    c.set("bar", "d")
    c.set("baz", "e")
    assert list(c._cache.items()) == [
        ((None, "boink"), (datetime.datetime(2020, 1, 1, 0, 0, 1), "will_prune")),
        ((None, "foo"), (datetime.datetime(2020, 1, 1, 0, 0, 2), "b")),
        ((None, "bar"), (datetime.datetime(2020, 1, 1, 0, 0, 3), "d")),
        ((None, "baz"), (datetime.datetime(2020, 1, 1, 0, 0, 4), "e")),
    ]

    c.get("foo")
    c.set("bozo", "y")
    c.set("bar", "f")
    c.set("bar2", "h")
    assert list(c._cache.items()) == [
        ((None, "baz"), (datetime.datetime(2020, 1, 1, 0, 0, 4), "e")),
        ((None, "foo"), (datetime.datetime(2020, 1, 1, 0, 0, 5), "b")),
        ((None, "bozo"), (datetime.datetime(2020, 1, 1, 0, 0, 6), "y")),
        ((None, "bar"), (datetime.datetime(2020, 1, 1, 0, 0, 7), "f")),
        ((None, "bar2"), (datetime.datetime(2020, 1, 1, 0, 0, 8), "h")),
    ]


class TestBucketTimestamp:
    DAY_IN_SECONDS = 60 * 60 * 24

    def test_docstring_examples(self):
        test_timestamps = [
            datetime.datetime(
                1970, 1, 1, 11, 22, tzinfo=datetime.timezone.utc
            ).timestamp(),
            datetime.datetime(
                1970, 1, 2, 0, 0, tzinfo=datetime.timezone.utc
            ).timestamp(),
            datetime.datetime(
                1970, 1, 7, 23, 59, tzinfo=datetime.timezone.utc
            ).timestamp(),
            datetime.datetime(
                1970, 1, 8, 0, 0, tzinfo=datetime.timezone.utc
            ).timestamp(),
            datetime.datetime(
                1970, 1, 12, 16, 0, tzinfo=datetime.timezone.utc
            ).timestamp(),
        ]
        expected_timestamps = [
            datetime.datetime(
                1970, 1, 8, 0, 0, tzinfo=datetime.timezone.utc
            ).timestamp(),
            datetime.datetime(
                1970, 1, 8, 0, 0, tzinfo=datetime.timezone.utc
            ).timestamp(),
            datetime.datetime(
                1970, 1, 8, 0, 0, tzinfo=datetime.timezone.utc
            ).timestamp(),
            datetime.datetime(
                1970, 1, 15, 0, 0, tzinfo=datetime.timezone.utc
            ).timestamp(),
            datetime.datetime(
                1970, 1, 15, 0, 0, tzinfo=datetime.timezone.utc
            ).timestamp(),
        ]
        with mock.patch(
            "time.time",
            side_effect=test_timestamps,
        ):
            for expected_timestamp in expected_timestamps:
                assert int(cache.bucket_timestamp(7), 10) == expected_timestamp

    def test_buckets_can_vary_by_interval(self):
        cache_timestamps = []
        mock_current_time = self.DAY_IN_SECONDS * 10
        with mock.patch("time.time", return_value=mock_current_time):
            for i in range(10):
                cache_timestamps.append(int(cache.bucket_timestamp(i), 10))

        expected_timestamps = [0] + [
            (int(mock_current_time / (self.DAY_IN_SECONDS * i)) + 1)
            * self.DAY_IN_SECONDS
            * i
            for i in range(1, 10)
        ]
        assert cache_timestamps == expected_timestamps

        # Time has advanced by less than a day, buckets should be the same
        with mock.patch(
            "time.time",
            return_value=mock_current_time + int(self.DAY_IN_SECONDS / 2),
        ):
            assert cache_timestamps == [
                int(cache.bucket_timestamp(i), 10) for i in range(10)
            ]


def test_clear_cache():
    # Test that the clear_cache function works
    day_in_seconds = 60 * 60 * 24

    # ensure cache directory exists
    cache_dir = environment.weave_filesystem_dir()
    if not os.path.exists(cache_dir):
        os.makedirs(cache_dir)

    # check cache directory file count
    orig_file_count = len(os.listdir(cache_dir))
    paths = []

    # create 10 cache directories
    # 5 in the past, 5 in the future
    for i in [-10, -9, -8, -7, -6, 1, 2, 3, 4, 5]:
        path = os.path.join(cache_dir, str(int(time.time() + (i * day_in_seconds))))
        paths.append(path)
        os.makedirs(path)

    # check cache directory file count is correct
    assert len(os.listdir(cache_dir)) == orig_file_count + len(paths)

    # clear the cache
    # should delete 5 past directories
    cache.clear_cache()

    # check cache directory file count is correct
    assert len(os.listdir(cache_dir)) == orig_file_count + len(paths) / 2

    # delete all created driectories
    for path in paths:
        if os.path.exists(path):
            os.rmdir(path)

    # Ensure cache directory is in the same state as before the test
    assert len(os.listdir(cache_dir)) == orig_file_count
