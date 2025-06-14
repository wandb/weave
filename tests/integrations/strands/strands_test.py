from weave.integrations.strands.strands_sdk import get_strands_patcher


def test_strands_patcher_init():
    """Test that the Strands patcher can be initialized."""
    patcher = get_strands_patcher()
    assert patcher is not None


def test_strands_patcher_disabled():
    """Test that the patcher can be disabled."""
    from weave.trace.autopatch import IntegrationSettings

    settings = IntegrationSettings(enabled=False)
    patcher = get_strands_patcher(settings)
    assert patcher.__class__.__name__ == "NoOpPatcher"


def test_strands_patcher_enabled():
    """Test that the patcher is enabled by default."""
    from weave.trace.autopatch import IntegrationSettings

    settings = IntegrationSettings(enabled=True)
    patcher = get_strands_patcher(settings)
    assert patcher.__class__.__name__ == "MultiPatcher"


def test_strands_postprocess_inputs():
    """Test input postprocessing for Strands calls."""
    from weave.integrations.strands.strands_sdk import strands_postprocess_inputs

    # Test with args containing a string prompt
    inputs = {"args": ("Tell me about AI",), "kwargs": {}}
    result = strands_postprocess_inputs(inputs)

    assert "prompt" in result
    assert result["prompt"] == "Tell me about AI"


def test_strands_call_display_name():
    """Test display name generation for Agent calls."""
    from weave.integrations.strands.strands_sdk import (
        default_call_display_name_agent_call,
    )

    # Mock call object
    class MockCall:
        def __init__(self, inputs):
            self.inputs = inputs

    # Test that display name is always just "Agent"
    call = MockCall({"prompt": "Tell me about AI"})
    result = default_call_display_name_agent_call(call)
    assert result == "Agent"

    # Test with args (positional argument)
    call = MockCall({"args": ("Tell me about AI",), "kwargs": {}})
    result = default_call_display_name_agent_call(call)
    assert result == "Agent"

    # Test without prompt
    call = MockCall({})
    result = default_call_display_name_agent_call(call)
    assert result == "Agent"


def test_strands_safe_serialization():
    """Test safe serialization of Strands objects."""
    from weave.integrations.strands.strands_sdk import safe_serialize_strands_object

    # Test primitive types
    assert safe_serialize_strands_object("test") == "test"
    assert safe_serialize_strands_object(42) == 42
    assert safe_serialize_strands_object(True) is True

    # Test type objects (which caused serialization errors)
    assert safe_serialize_strands_object(str) == "<class 'str'>"

    # Test complex object
    class MockAgent:
        def __init__(self):
            self.name = "test_agent"
            self.model_id = "gpt-4"

    agent = MockAgent()
    serialized = safe_serialize_strands_object(agent)
    assert isinstance(serialized, dict)
    assert serialized["type"] == "MockAgent"
    assert serialized["name"] == "test_agent"
    assert serialized["model_id"] == "gpt-4"
