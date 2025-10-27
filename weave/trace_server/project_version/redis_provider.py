"""Redis-backed project version provider."""

from typing import Any, Optional

from weave.trace_server.project_version.types import ProjectVersion


class RedisProjectVersionProvider:
    """Reads project version from Redis cache.

    Args:
        redis_client: Async Redis client instance.
        enabled: Feature flag to enable Redis lookups.

    Raises:
        Exception: If Redis is disabled or the key is not found.

    Examples:
        >>> redis_provider = RedisProjectVersionProvider(
        ...     redis_client=redis.from_url("redis://localhost"),
        ...     enabled=True,
        ... )
        >>> version = await redis_provider.get_project_version("proj-123")
    """

    def __init__(
        self,
        redis_client: Optional[Any],
        enabled: bool,
    ):
        self._enabled = enabled
        self._redis = redis_client

    async def get_project_version(
        self, project_id: str, is_write: bool = False
    ) -> ProjectVersion:
        """Get project version from Redis cache.

        Args:
            project_id: The project identifier.
            is_write: Whether this is for a write operation (unused in this provider).

        Returns:
            Union[ProjectVersion, int]: The cached version (0, 1, or -1).

        Raises:
            Exception: If Redis is disabled, unavailable, or key not found.
        """
        if not self._enabled or self._redis is None:
            raise ValueError("Redis is disabled or unavailable")

        key = f"weave:project_version:{project_id}"
        cached = await self._redis.get(key)
        if cached is None:
            raise ValueError(f"Project {project_id} not found in Redis")

        return ProjectVersion(int(cached))
