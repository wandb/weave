from weave.shared.trace_server_interface_util import extract_refs_from_values

REF_A = "weave-trace-internal:///test_project/object/obj_a:abc123"
REF_B = "weave-trace-internal:///test_project/object/obj_b:def456"


def test_extract_refs_from_values_deduplicates():
    """Requirement: input_refs/output_refs must not contain duplicate ref URIs.
    Interface: extract_refs_from_values(vals) -> list[str]
    Given: inputs containing the same ref URI multiple times via different structures
    When: extract_refs_from_values is called
    Then: each ref URI appears at most once in the result
    """
    # Same ref twice as sibling dict values
    assert extract_refs_from_values({"a": REF_A, "b": REF_A}) == [REF_A]

    # Same ref twice in a list
    assert extract_refs_from_values([REF_A, REF_A]) == [REF_A]

    # Same ref in nested structures
    assert extract_refs_from_values({"x": {"nested": REF_A}, "y": REF_A}) == [REF_A]

    # Multiple distinct refs — each appears exactly once
    result = extract_refs_from_values({"a": REF_A, "b": REF_B})
    assert sorted(result) == sorted([REF_A, REF_B])
    assert len(result) == 2

    # No refs — empty result
    assert extract_refs_from_values({"a": "hello", "b": 42}) == []
