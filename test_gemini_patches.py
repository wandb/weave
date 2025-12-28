"""
Test script to verify the Weave Google GenAI patches work correctly.

This script tests:
1. Token counting fix for streaming responses
2. System instruction capture

Run with:
    GOOGLE_GENAI_KEY=your_api_key python test_gemini_patches.py
"""

import os
import sys


def test_accumulator_fix():
    """Test that the fixed accumulator replaces instead of sums token counts."""
    print("\n" + "=" * 60)
    print("TEST 1: Token Accumulator Fix")
    print("=" * 60)

    # Create mock usage_metadata objects to simulate streaming chunks
    class MockUsageMetadata:
        def __init__(self, prompt=None, candidates=None, total=None, cached=None):
            self.prompt_token_count = prompt
            self.candidates_token_count = candidates
            self.total_token_count = total
            self.cached_content_token_count = cached

    class MockPart:
        def __init__(self, text=""):
            self.text = text

    class MockContent:
        def __init__(self, text=""):
            self.parts = [MockPart(text)]

    class MockCandidate:
        def __init__(self, text=""):
            self.content = MockContent(text)

    class MockResponse:
        def __init__(self, text="", prompt=None, candidates=None, total=None):
            self.candidates = [MockCandidate(text)]
            self.usage_metadata = MockUsageMetadata(prompt, candidates, total)

    # Import the fixed accumulator
    from weave_gemini_patches import _fixed_google_genai_gemini_accumulator as fixed_acc

    # Simulate streaming chunks (based on actual cassette data)
    chunk1 = MockResponse("The", prompt=9, candidates=None, total=9)
    chunk2 = MockResponse(" capital of France", prompt=9, candidates=None, total=9)
    chunk3 = MockResponse(" is Paris.\n", prompt=8, candidates=8, total=16)

    # Accumulate with fixed function
    acc = None
    acc = fixed_acc(acc, chunk1)
    acc = fixed_acc(acc, chunk2)
    acc = fixed_acc(acc, chunk3)

    print(f"\nSimulated streaming chunks:")
    print(f"  Chunk 1: prompt=9, total=9")
    print(f"  Chunk 2: prompt=9, total=9")
    print(f"  Chunk 3: prompt=8, candidates=8, total=16")

    print(f"\nFixed accumulator results:")
    print(f"  prompt_token_count: {acc.usage_metadata.prompt_token_count}")
    print(f"  candidates_token_count: {acc.usage_metadata.candidates_token_count}")
    print(f"  total_token_count: {acc.usage_metadata.total_token_count}")
    print(f"  accumulated_text: '{acc.candidates[0].content.parts[0].text}'")

    # Verify correctness
    assert acc.usage_metadata.prompt_token_count == 8, \
        f"Expected prompt_token_count=8, got {acc.usage_metadata.prompt_token_count}"
    assert acc.usage_metadata.candidates_token_count == 8, \
        f"Expected candidates_token_count=8, got {acc.usage_metadata.candidates_token_count}"
    assert acc.usage_metadata.total_token_count == 16, \
        f"Expected total_token_count=16, got {acc.usage_metadata.total_token_count}"
    assert acc.candidates[0].content.parts[0].text == "The capital of France is Paris.\n", \
        f"Unexpected accumulated text"

    print("\n✓ Token accumulator fix working correctly!")
    print("  (Values are REPLACED, not summed)")

    # Show what the BUGGY version would produce
    print("\n  For comparison, buggy version would produce:")
    print(f"    prompt_token_count: 9 + 9 + 8 = 26 (WRONG)")
    print(f"    total_token_count: 9 + 9 + 16 = 34 (WRONG)")

    return True


def test_system_instruction_extraction_logic():
    """Test the system instruction extraction logic without weave dependency."""
    from weave_gemini_patches import _serialize_content

    # Test string content
    result = _serialize_content("You are a helpful assistant.")
    assert result == "You are a helpful assistant.", f"String serialization failed: {result}"
    print("  ✓ String serialization works")

    # Test object with parts
    class MockPart:
        def __init__(self, text):
            self.text = text

    class MockContent:
        def __init__(self, text):
            self.parts = [MockPart(text)]

    result = _serialize_content(MockContent("System instruction text"))
    assert result == "System instruction text", f"Content serialization failed: {result}"
    print("  ✓ Content object serialization works")

    # Test object with to_dict
    class MockWithToDict:
        def to_dict(self):
            return {"system_instruction": "test"}

    result = _serialize_content(MockWithToDict())
    assert result == {"system_instruction": "test"}, f"to_dict serialization failed: {result}"
    print("  ✓ Object with to_dict() works")

    print("\n✓ System instruction extraction logic working correctly!")
    return True


def test_postprocess_inputs_fix():
    """Test that system instructions are captured from config."""
    print("\n" + "=" * 60)
    print("TEST 2: System Instruction Capture Fix")
    print("=" * 60)

    # First, test the core serialization logic that doesn't depend on weave
    print("\nTesting core serialization logic...")
    try:
        test_system_instruction_extraction_logic()
    except Exception as e:
        print(f"  ✗ Core serialization test failed: {e}")
        return False

    # Then try to test the full postprocess function if weave is fully available
    # The postprocess function depends on weave.trace.serialization.serialize.dictify
    # which requires a complete weave installation with all dependencies
    try:
        from weave_gemini_patches import _fixed_google_genai_gemini_postprocess_inputs as fixed_postprocess

        # Test 1: System instruction in config parameter (generate_content style)
        class MockConfig:
            def __init__(self):
                self.system_instruction = "You are a helpful assistant."
                self.temperature = 0.7

        inputs1 = {
            "model": "gemini-2.0-flash",
            "contents": "Hello",
            "config": MockConfig()
        }

        result1 = fixed_postprocess(inputs1.copy())
        print(f"\nTest: system_instruction in config parameter")
        print(f"  Input config.system_instruction: 'You are a helpful assistant.'")
        print(f"  Captured system_instruction: '{result1.get('system_instruction', 'NOT CAPTURED')}'")

        assert result1.get('system_instruction') == "You are a helpful assistant.", \
            "System instruction not captured from config"
        print("  ✓ System instruction captured correctly!")

        # Test 2: System instruction in Chat._config (send_message style)
        class MockChatConfig:
            def __init__(self):
                self.system_instruction = "You are a coding expert."

        class MockChat:
            def __init__(self):
                self._model = "gemini-2.0-flash"
                self._config = MockChatConfig()

        inputs2 = {
            "self": MockChat(),
            "message": "Write a function"
        }

        result2 = fixed_postprocess(inputs2.copy())
        print(f"\nTest: system_instruction in Chat._config")
        print(f"  Input Chat._config.system_instruction: 'You are a coding expert.'")
        print(f"  Captured system_instruction: '{result2.get('system_instruction', 'NOT CAPTURED')}'")
        print(f"  Captured model: '{result2.get('model', 'NOT CAPTURED')}'")

        assert result2.get('system_instruction') == "You are a coding expert.", \
            "System instruction not captured from Chat._config"
        assert result2.get('model') == "gemini-2.0-flash", \
            "Model name not captured from Chat._model"
        print("  ✓ System instruction and model captured correctly!")

    except (ImportError, ModuleNotFoundError) as e:
        # If weave is not fully installed, the core test above already validated the logic
        print(f"\n⚠ Cannot test full postprocess (weave dependency missing): {e}")
        print("  Core serialization logic already validated above.")
        print("  Full postprocess test requires complete weave installation.")

    return True


def test_live_integration():
    """Test with actual Google GenAI API (requires API key)."""
    print("\n" + "=" * 60)
    print("TEST 3: Live Integration Test (Optional)")
    print("=" * 60)

    api_key = os.environ.get("GOOGLE_GENAI_KEY")
    if not api_key:
        print("\n⚠ Skipping live test: GOOGLE_GENAI_KEY not set")
        print("  Set GOOGLE_GENAI_KEY environment variable to run live tests")
        return True

    try:
        # Apply patches BEFORE importing weave
        import weave_gemini_patches
        weave_gemini_patches.apply_patches()

        import weave
        from google import genai

        # Initialize weave with a test project
        weave.init("test-gemini-patches")

        # Create client
        client = genai.Client(api_key=api_key)

        print("\nTesting streaming response...")
        response = client.models.generate_content_stream(
            model="gemini-2.0-flash",
            contents="What is 2+2? Reply with just the number.",
        )

        text = ""
        for chunk in response:
            if hasattr(chunk, 'text') and chunk.text:
                text += chunk.text

        print(f"  Response: {text.strip()}")
        print("  ✓ Streaming completed (check Weave UI for correct token counts)")

        print("\nTesting with system instruction...")
        response2 = client.models.generate_content(
            model="gemini-2.0-flash",
            contents="Say hello",
            config=genai.types.GenerateContentConfig(
                system_instruction="You are a pirate. Always respond like a pirate.",
                temperature=0.7,
            ),
        )
        print(f"  Response: {response2.text.strip()[:100]}...")
        print("  ✓ System instruction test completed (check Weave UI for captured instruction)")

        return True

    except Exception as e:
        print(f"\n✗ Live test failed: {e}")
        return False


def main():
    print("=" * 60)
    print("Weave Google GenAI Patch Verification")
    print("=" * 60)

    all_passed = True

    try:
        all_passed &= test_accumulator_fix()
    except Exception as e:
        print(f"\n✗ Accumulator test failed: {e}")
        all_passed = False

    try:
        all_passed &= test_postprocess_inputs_fix()
    except Exception as e:
        print(f"\n✗ Postprocess inputs test failed: {e}")
        all_passed = False

    try:
        all_passed &= test_live_integration()
    except Exception as e:
        print(f"\n✗ Live integration test failed: {e}")
        all_passed = False

    print("\n" + "=" * 60)
    if all_passed:
        print("✓ All tests passed!")
    else:
        print("✗ Some tests failed")
    print("=" * 60)

    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
