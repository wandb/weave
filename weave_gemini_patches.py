"""
Monkey patches for Weave SDK's Google GenAI integration.

These patches fix two issues:
1. Token overcounting in streaming responses (tokens were being summed instead of replaced)
2. System prompt not being captured in traces

USAGE:
    # Apply these patches BEFORE calling weave.init()
    import weave_gemini_patches
    weave_gemini_patches.apply_patches()

    import weave
    weave.init("my-project")

    # Now use Google GenAI as normal
    from google import genai
    client = genai.Client(api_key="...")
    response = client.models.generate_content(...)

IMPORTANT: These patches MUST be applied before weave.init() is called,
because weave.init() triggers the automatic patching of the Google GenAI SDK.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Optional

if TYPE_CHECKING:
    from google.genai.types import GenerateContentResponse


def _fixed_google_genai_gemini_accumulator(
    acc: Optional["GenerateContentResponse"], value: "GenerateContentResponse"
) -> "GenerateContentResponse":
    """
    Fixed accumulator for Google GenAI streaming responses.

    The original implementation incorrectly SUMS token counts from each chunk,
    but the Gemini API returns cumulative counts in each chunk (or only in the
    final chunk). This fix REPLACES token counts with the latest non-None values.

    See: https://ai.google.dev/gemini-api/docs/tokens
    "When streaming output, the usageMetadata attribute only appears on the
    last chunk of the stream."
    """
    if acc is None:
        return value

    # Accumulate text content from candidates (this part was correct)
    for i, value_candidate in enumerate(value.candidates):
        if i >= len(acc.candidates):
            break
        # Handle cases where content or parts might be None
        if not hasattr(value_candidate, 'content') or value_candidate.content is None:
            continue
        if not hasattr(value_candidate.content, 'parts') or value_candidate.content.parts is None:
            continue
        if not hasattr(acc.candidates[i], 'content') or acc.candidates[i].content is None:
            continue
        if not hasattr(acc.candidates[i].content, 'parts') or acc.candidates[i].content.parts is None:
            continue

        for j, value_part in enumerate(value_candidate.content.parts):
            if j >= len(acc.candidates[i].content.parts):
                break
            if hasattr(value_part, 'text') and value_part.text is not None:
                if hasattr(acc.candidates[i].content.parts[j], 'text'):
                    acc.candidates[i].content.parts[j].text += value_part.text

    # FIX: REPLACE token counts with latest non-None values instead of adding
    # The Gemini API returns cumulative counts, not incremental ones
    if hasattr(value, 'usage_metadata') and value.usage_metadata is not None:
        if hasattr(acc, 'usage_metadata') and acc.usage_metadata is not None:
            if value.usage_metadata.prompt_token_count is not None:
                acc.usage_metadata.prompt_token_count = value.usage_metadata.prompt_token_count

            if value.usage_metadata.candidates_token_count is not None:
                acc.usage_metadata.candidates_token_count = value.usage_metadata.candidates_token_count

            if value.usage_metadata.total_token_count is not None:
                acc.usage_metadata.total_token_count = value.usage_metadata.total_token_count

            if hasattr(value.usage_metadata, 'cached_content_token_count') and \
               value.usage_metadata.cached_content_token_count is not None:
                acc.usage_metadata.cached_content_token_count = value.usage_metadata.cached_content_token_count

    return acc


def _fixed_google_genai_gemini_postprocess_inputs(inputs: dict[str, Any]) -> dict[str, Any]:
    """
    Fixed postprocess_inputs that also extracts system instructions.

    The original implementation only extracted the model name and serialized 'self'.
    This fix also explicitly extracts system_instruction from the config parameter
    and from Chat objects to ensure it appears in traces.
    """
    from weave.trace.serialization.serialize import dictify

    # Extract the model name from the inputs and ensure it is present in the inputs
    if "self" in inputs:
        model_name = getattr(inputs["self"], "_model", None)
        if model_name is not None:
            inputs["model"] = model_name

        # For Chat objects, extract system instruction from the config
        self_obj = inputs["self"]

        # Try to extract system instruction from Chat._config
        if hasattr(self_obj, '_config') and self_obj._config is not None:
            config = self_obj._config
            system_instruction = None

            # Try different ways the system instruction might be stored
            if hasattr(config, 'system_instruction'):
                system_instruction = config.system_instruction
            elif isinstance(config, dict) and 'system_instruction' in config:
                system_instruction = config['system_instruction']

            if system_instruction is not None:
                inputs["system_instruction"] = _serialize_content(system_instruction)

        # Convert the `self` parameter to a dictionary
        inputs["self"] = dictify(inputs["self"])

    # Also check for system_instruction in the config parameter (for generate_content calls)
    if "config" in inputs and inputs["config"] is not None:
        config = inputs["config"]
        system_instruction = None

        if hasattr(config, 'system_instruction') and config.system_instruction is not None:
            system_instruction = config.system_instruction
        elif isinstance(config, dict) and config.get('system_instruction') is not None:
            system_instruction = config['system_instruction']

        if system_instruction is not None:
            inputs["system_instruction"] = _serialize_content(system_instruction)

    return inputs


def _serialize_content(content: Any) -> Any:
    """Helper to serialize Content/Part objects to a readable format."""
    if content is None:
        return None

    # If it's a string, return as-is
    if isinstance(content, str):
        return content

    # If it has a to_dict method (Pydantic model), use it
    if hasattr(content, 'to_dict'):
        try:
            return content.to_dict()
        except Exception:
            pass

    # If it has a model_dump method (Pydantic v2), use it
    if hasattr(content, 'model_dump'):
        try:
            return content.model_dump()
        except Exception:
            pass

    # If it has parts attribute (Content object), extract text from parts
    if hasattr(content, 'parts'):
        parts = content.parts
        if parts:
            texts = []
            for part in parts:
                if hasattr(part, 'text') and part.text:
                    texts.append(part.text)
            if texts:
                return '\n'.join(texts) if len(texts) > 1 else texts[0]

    # Fallback to string representation
    return str(content)


def apply_patches() -> None:
    """
    Apply the monkey patches to fix Google GenAI integration issues.

    MUST be called BEFORE weave.init() for the patches to take effect.
    """
    try:
        import weave.integrations.google_genai.gemini_utils as gemini_utils

        # Store original functions for potential restoration
        gemini_utils._original_accumulator = gemini_utils.google_genai_gemini_accumulator
        gemini_utils._original_postprocess_inputs = gemini_utils.google_genai_gemini_postprocess_inputs

        # Apply the fixed functions
        gemini_utils.google_genai_gemini_accumulator = _fixed_google_genai_gemini_accumulator
        gemini_utils.google_genai_gemini_postprocess_inputs = _fixed_google_genai_gemini_postprocess_inputs

        print("✓ Weave Google GenAI patches applied successfully")
        print("  - Fixed: Token overcounting in streaming responses")
        print("  - Fixed: System instruction capture in traces")

    except ImportError as e:
        print(f"⚠ Could not apply Weave patches: {e}")
        print("  Make sure weave is installed: pip install weave")


def restore_original() -> None:
    """
    Restore the original (buggy) functions if needed.

    Note: This only works if the patches were applied before weave.init().
    If weave.init() has already been called, the patchers have already
    captured references to the functions.
    """
    try:
        import weave.integrations.google_genai.gemini_utils as gemini_utils

        if hasattr(gemini_utils, '_original_accumulator'):
            gemini_utils.google_genai_gemini_accumulator = gemini_utils._original_accumulator
        if hasattr(gemini_utils, '_original_postprocess_inputs'):
            gemini_utils.google_genai_gemini_postprocess_inputs = gemini_utils._original_postprocess_inputs

        print("✓ Original functions restored")

    except ImportError:
        pass


# Also provide a patch for Vertex AI which has the same token accumulation bug
def apply_vertexai_patches() -> None:
    """
    Apply monkey patches to fix Vertex AI integration token overcounting.

    MUST be called BEFORE weave.init() for the patches to take effect.
    """
    try:
        import weave.integrations.vertexai.vertexai_sdk as vertexai_sdk
        from google.cloud.aiplatform_v1beta1.types import content as gapic_content_types
        from google.cloud.aiplatform_v1beta1.types import (
            prediction_service as gapic_prediction_service_types,
        )
        from vertexai.generative_models import GenerationResponse

        def _fixed_vertexai_accumulator(
            acc: GenerationResponse | None, value: GenerationResponse
        ) -> GenerationResponse:
            """Fixed Vertex AI accumulator that replaces instead of sums token counts."""
            if acc is None:
                return value

            candidates = []
            for i, value_candidate in enumerate(value.candidates):
                accumulated_texts = []
                for j, value_part in enumerate(value_candidate.content.parts):
                    accumulated_text = acc.candidates[i].content.parts[j].text + value_part.text
                    accumulated_texts.append(accumulated_text)
                parts = [gapic_content_types.Part(text=text) for text in accumulated_texts]
                content = gapic_content_types.Content(
                    role=value_candidate.content.role, parts=parts
                )
                candidate = gapic_content_types.Candidate(content=content)
                candidates.append(candidate)
            accumulated_response = gapic_prediction_service_types.GenerateContentResponse(
                candidates=candidates
            )
            acc = GenerationResponse._from_gapic(accumulated_response)

            # FIX: REPLACE token counts instead of adding
            if value.usage_metadata.prompt_token_count is not None:
                acc.usage_metadata.prompt_token_count = value.usage_metadata.prompt_token_count
            if value.usage_metadata.candidates_token_count is not None:
                acc.usage_metadata.candidates_token_count = value.usage_metadata.candidates_token_count
            if value.usage_metadata.total_token_count is not None:
                acc.usage_metadata.total_token_count = value.usage_metadata.total_token_count

            return acc

        # Store original and apply fix
        vertexai_sdk._original_accumulator = vertexai_sdk.vertexai_accumulator
        vertexai_sdk.vertexai_accumulator = _fixed_vertexai_accumulator

        print("✓ Weave Vertex AI patches applied successfully")
        print("  - Fixed: Token overcounting in streaming responses")

    except ImportError as e:
        print(f"⚠ Could not apply Vertex AI patches: {e}")


def apply_all_patches() -> None:
    """Apply all available patches for Google AI integrations."""
    apply_patches()
    try:
        apply_vertexai_patches()
    except Exception:
        pass  # Vertex AI may not be installed


if __name__ == "__main__":
    print("Weave Google GenAI Monkey Patches")
    print("=" * 40)
    print()
    print("Usage:")
    print("  import weave_gemini_patches")
    print("  weave_gemini_patches.apply_patches()")
    print("  ")
    print("  import weave")
    print("  weave.init('my-project')")
    print()
    print("Note: Patches must be applied BEFORE weave.init()")
