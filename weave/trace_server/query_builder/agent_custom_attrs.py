"""Small SQL helpers shared by agent custom-attribute query builders."""

from __future__ import annotations


def custom_attr_value_or_null(alias: str, map_col: str, key_slot: str) -> str:
    """Read a ClickHouse Map key as NULL when the key is absent."""
    source = f"{alias}.{map_col}"
    return f"if(mapContains({source}, {key_slot}), {source}[{key_slot}], NULL)"
