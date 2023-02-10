import typing
import datetime

from . import engine_trace
from . import wandb_api
from . import environment
from . import errors

statsd = engine_trace.statsd()  # type: ignore


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
