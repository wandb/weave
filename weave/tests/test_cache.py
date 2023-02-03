import datetime

from .. import cache


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
