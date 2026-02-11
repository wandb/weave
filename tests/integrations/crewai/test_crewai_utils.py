"""Tests for crewai_utils serialization functions.

These tests verify that CrewAI object serialization uses bounded depth
to prevent hangs when tracing complex CrewAI object graphs (GitHub #5158).
"""

from __future__ import annotations

from weave.integrations.crewai.crewai_utils import (
    crew_kickoff_postprocess_inputs,
    safe_serialize_crewai_object,
)


class DeeplyNestedObj:
    """A plain object with deeply nested children, simulating a complex CrewAI object."""

    def __init__(self, depth: int = 0, max_depth: int = 10) -> None:
        self.value = f"level_{depth}"
        if depth < max_depth:
            self.child = DeeplyNestedObj(depth + 1, max_depth)


def _count_dict_depth(result: object) -> int:
    """Walk down the 'child' chain and count how many levels are dicts."""
    current = result
    depth = 0
    while isinstance(current, dict) and "child" in current:
        current = current["child"]
        depth += 1
    return depth


def test_safe_serialize_crewai_object_limits_depth_for_unknown_types() -> None:
    """
    Requirement: Unknown objects (not Agent/Task) must be serialized with bounded depth
    Interface: safe_serialize_crewai_object()
    Given: An unknown object type with deep nesting (50 levels)
    When: safe_serialize_crewai_object() is called
    Then: The result should be depth-limited (stringified well before 50 levels)
    """
    obj = DeeplyNestedObj(depth=0, max_depth=50)
    result = safe_serialize_crewai_object(obj)
    depth = _count_dict_depth(result)

    # With bounded depth, we should NOT reach all 50 levels as dicts.
    # The chain should be cut off well before depth 50.
    assert depth < 50, (
        f"dictify traversed {depth} levels deep without limit. "
        "Expected depth-limited serialization to prevent hangs on complex objects."
    )


def test_crew_kickoff_postprocess_inputs_limits_depth_for_object_inputs() -> None:
    """
    Requirement: The 'inputs' field must be depth-limited to prevent hangs
    Interface: crew_kickoff_postprocess_inputs()
    Given: A kickoff inputs dict where 'inputs' contains a deeply nested object (50 levels)
    When: crew_kickoff_postprocess_inputs() is called
    Then: The 'inputs' field should be depth-limited (well before 50 levels)
    """
    obj = DeeplyNestedObj(depth=0, max_depth=50)
    inputs = {"inputs": obj}
    result = crew_kickoff_postprocess_inputs(inputs)
    depth = _count_dict_depth(result["inputs"])

    # With bounded depth, we should NOT reach all 50 levels as dicts.
    assert depth < 50, (
        f"dictify traversed {depth} levels deep without limit. "
        "Expected depth-limited serialization to prevent hangs on complex objects."
    )
