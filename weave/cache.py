import typing
import contextlib
import datetime
import logging
import shutil
import time
import os

from . import context_state
from . import engine_trace
from . import environment
from . import errors
from . import wandb_api

statsd = engine_trace.statsd()  # type: ignore
logger = logging.getLogger("root")

"""
Returns a timestamp bucketed by interval days that is calculated from epoch time. For example, if we want
a bucket interval of 1 day, the anytime this function is called between 0 and 86399 seconds during the first
day of unix time (Jan 1 1970), it will return Jan 2 1970. This function returns the END time of the bucket
so it is easier for the caller to know when a cache interval will no longer be used. 

For another example, if we want a bucket interval of 7 days, then here are some example values:
system time             bucketed time
11:22 Jan 1 1970       00:00 Jan 8 1970
23:59 Jan 7 1970       00:00 Jan 14 1970
00:00 Jan 8 1970       00:00 Jan 15 1970
16:00 Jan 12 1970      00:00 Jan 19 1970
12:00 Jan 3 2024       00:00 Jan 10 2024
"""


def bucket_timestamp(interval_days: int) -> str:
    if interval_days == 0:
        return "0"
    now = time.time()
    interval_seconds = interval_days * 24 * 60 * 60
    num_intervals = int(now / interval_seconds)
    # use the bucket end time because this makes it easy to know when a cache interval will no longer be used
    bucket_end_time = (num_intervals + 1) * interval_seconds
    return str(
        datetime.datetime.fromtimestamp(bucket_end_time, datetime.timezone.utc)
        .timestamp()
        .__floor__()
    )


@contextlib.contextmanager
def time_interval_cache_prefix(
    cache_prefix_input: typing.Optional[str] = None,
) -> typing.Generator[None, None, None]:
    cache_prefix = cache_prefix_input
    if cache_prefix is None:
        duration = environment.cache_duration_days()
        if duration != 0:
            cache_prefix = bucket_timestamp(duration)
            logger.info(f"New cache prefix {cache_prefix}")
    token = context_state._cache_prefix_context.set(cache_prefix)
    try:
        yield
    finally:
        context_state._cache_prefix_context.reset(token)


def get_cache_prefix_context() -> typing.Optional[str]:
    return context_state._cache_prefix_context.get()


def clear_cache() -> None:
    # Read the directory address and threshold from the environment variable
    directory_path = environment.weave_filesystem_dir()

    now = datetime.datetime.now().timestamp()
    # buffer is in seconds
    buffer = 60 * 60 * 24 * environment.cache_deletion_buffer_days()  # days of buffer

    # Validate the directory path
    if not directory_path:
        logging.info("WEAVE_PYTHON_CACHE is not set.")
        return
    if not os.path.isdir(directory_path):
        logging.info(f"{directory_path} is not a valid directory.")
        return

    # for each cache in the directory, check if its expired past the buffer
    for item in os.listdir(directory_path):
        try:
            item_timestamp = int(item)
            item_path = os.path.join(directory_path, item)

            # If the item is expired and we are past the buffer, delete it
            if item_timestamp + buffer < now:
                # Delete the data
                shutil.rmtree(item_path)
                logging.info(f"Deleted {item}.")
        except:
            logging.info(f"Error deleting {item}.")
            continue


def get_user_cache_key() -> typing.Optional[str]:
    ctx = wandb_api.get_wandb_api_context()
    if ctx is None:
        if environment.is_public():
            raise errors.WeaveAccessDeniedError("No user set in public environment")
        return None
    return ctx.user_id


# TODO: stats, test

CacheKeyType = typing.TypeVar("CacheKeyType")
CacheValueType = typing.TypeVar("CacheValueType")


class LruTimeWindowCache(typing.Generic[CacheKeyType, CacheValueType]):
    """A cache that stores values for a fixed amount of time.

    Respects the user cache key, so that different users don't share the same cache.
    """

    class NotFound:
        pass

    NOT_FOUND = NotFound()

    def __init__(
        self,
        max_age: datetime.timedelta,
        now_fn: typing.Callable[[], datetime.datetime] = datetime.datetime.now,
    ) -> None:
        self.max_age = max_age
        self._now_fn = now_fn

        # Items are time ordered, with oldest at the front.
        self._cache: dict[
            typing.Tuple[typing.Optional[str], CacheKeyType],
            typing.Tuple[datetime.datetime, CacheValueType],
        ] = {}

    def _full_key(
        self, key: CacheKeyType
    ) -> typing.Tuple[typing.Optional[str], CacheKeyType]:
        return (get_user_cache_key(), key)

    def _prune(self, now: datetime.datetime) -> None:
        for key, val in list(self._cache.items()):
            if now - val[0] > self.max_age:
                del self._cache[key]
            else:
                break
        statsd.gauge("weave.cache.size", len(self._cache))

    def get(self, key: CacheKeyType) -> typing.Union[NotFound, CacheValueType]:
        full_key = self._full_key(key)
        val = self._cache.get(full_key)
        if val is None:
            statsd.increment("weave.cache.miss")
            return self.NOT_FOUND
        # Set the value again to move it to the end of the cache
        self.set(key, val[1])
        statsd.increment("weave.cache.hit")
        return val[1]

    def set(self, key: CacheKeyType, value: CacheValueType) -> None:
        full_key = self._full_key(key)
        now = self._now_fn()
        if full_key in self._cache:
            # Delete so we move to the end of the cache
            del self._cache[full_key]
        self._cache[full_key] = (now, value)
        self._prune(now)
