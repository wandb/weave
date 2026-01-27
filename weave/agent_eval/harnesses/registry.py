"""Harness adapter registry."""

from __future__ import annotations

from typing import TYPE_CHECKING

from .base import HarnessAdapter

if TYPE_CHECKING:
    from ..config.schema import HarnessConfig, HarnessType

# Registry of harness adapters
_REGISTRY: dict[str, type[HarnessAdapter]] = {}


def register_harness(name: str):
    """Decorator to register a harness adapter.

    Args:
        name: The harness type name (e.g., 'codex').

    Returns:
        Decorator function.
    """
    def decorator(cls: type[HarnessAdapter]) -> type[HarnessAdapter]:
        _REGISTRY[name] = cls
        return cls
    return decorator


def get_harness(config: HarnessConfig) -> HarnessAdapter:
    """Get a harness adapter instance for the given config.

    Args:
        config: Harness configuration.

    Returns:
        HarnessAdapter instance.

    Raises:
        ValueError: If harness type is not registered.
    """
    # Handle both enum and string types
    harness_type = config.type.value if hasattr(config.type, "value") else str(config.type)
    if harness_type not in _REGISTRY:
        raise ValueError(
            f"Unknown harness type: {harness_type}. "
            f"Available: {list(_REGISTRY.keys())}"
        )
    return _REGISTRY[harness_type]()


def list_harnesses() -> list[str]:
    """List all registered harness types.

    Returns:
        List of harness type names.
    """
    return list(_REGISTRY.keys())


# Import adapters to trigger registration
def _load_adapters():
    """Load all adapter modules to register them."""
    from . import codex, claude, opencode, generic  # noqa: F401


_load_adapters()
