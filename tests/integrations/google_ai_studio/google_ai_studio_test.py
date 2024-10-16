import os

import pytest

from weave.integrations.integration_utilities import op_name_from_ref


# NOTE: These asserts are slightly more relaxed than other integrations because we can't yet save
# the output with vcrpy.  When VCR.py supports GRPC, we should add recordings for these tests!
# NOTE: We have retries because these tests are not deterministic (they use the live Gemini APIs),
# which can sometimes fail unexpectedly.
def assert_correct_output_shape(output: dict):
    assert "candidates" in output
    assert isinstance(output["candidates"], list)
    for candidate in output["candidates"]:
        assert isinstance(parts := candidate["content"]["parts"], list)
        for part in parts:
            assert isinstance(part["text"], str)

        # https://cloud.google.com/vertex-ai/generative-ai/docs/reference/python/latest/vertexai.preview.generative_models.FinishReason
        # 0 is FINISH_REASON_UNSPECIFIED
        # 1 is STOP
        assert candidate["finish_reason"] in (0, 1)
        assert isinstance(candidate["index"], int)
        assert isinstance(candidate["safety_ratings"], list)
        assert isinstance(candidate["token_count"], int)
        assert isinstance(candidate["grounding_attributions"], list)
        assert isinstance(candidate["avg_logprobs"], float)
    assert isinstance(output["usage_metadata"], dict)
    assert isinstance(output["usage_metadata"]["prompt_token_count"], int)
    assert isinstance(output["usage_metadata"]["candidates_token_count"], int)
    assert isinstance(output["usage_metadata"]["total_token_count"], int)
    assert isinstance(output["usage_metadata"]["cached_content_token_count"], int)


def assert_correct_summary(summary: dict, trace_name: str):
    assert "usage" in summary
    assert "gemini-1.5-flash" in summary["usage"]
    assert summary["usage"]["gemini-1.5-flash"]["requests"] == 1
    assert summary["usage"]["gemini-1.5-flash"]["prompt_tokens"] > 0
    assert summary["usage"]["gemini-1.5-flash"]["completion_tokens"] > 0
    assert summary["usage"]["gemini-1.5-flash"]["total_tokens"] > 0

    assert "weave" in summary
    assert summary["weave"]["status"] == "success"
    assert summary["weave"]["trace_name"] == trace_name
    assert summary["weave"]["latency_ms"] > 0


@pytest.mark.retry(max_attempts=5)
@pytest.mark.skip_clickhouse_client
def test_content_generation(client):
    import google.generativeai as genai

    genai.configure(api_key=os.getenv("GOOGLE_GENAI_KEY"))
    model = genai.GenerativeModel("gemini-1.5-flash")
    model.generate_content("Explain how AI works in simple terms")

    calls = list(client.calls())
    assert len(calls) == 1

    call = calls[0]
    assert call.started_at < call.ended_at

    trace_name = op_name_from_ref(call.op_name)
    assert trace_name == "google.generativeai.GenerativeModel.generate_content"
    assert call.output is not None
    assert_correct_output_shape(call.output)
    assert_correct_summary(call.summary, trace_name)


@pytest.mark.retry(max_attempts=5)
@pytest.mark.skip_clickhouse_client
def test_content_generation_stream(client):
    import google.generativeai as genai

    genai.configure(api_key=os.getenv("GOOGLE_GENAI_KEY"))
    model = genai.GenerativeModel("gemini-1.5-flash")
    response = model.generate_content(
        "Explain how AI works in simple terms", stream=True
    )
    chunks = [chunk.text for chunk in response]
    assert len(chunks) > 1

    calls = list(client.calls())
    assert len(calls) == 1

    call = calls[0]
    assert call.started_at < call.ended_at

    trace_name = op_name_from_ref(call.op_name)
    assert trace_name == "google.generativeai.GenerativeModel.generate_content"
    assert call.output is not None
    assert_correct_output_shape(call.output)
    assert_correct_summary(call.summary, trace_name)


@pytest.mark.retry(max_attempts=5)
@pytest.mark.asyncio
@pytest.mark.skip_clickhouse_client
async def test_content_generation_async(client):
    import google.generativeai as genai

    genai.configure(api_key=os.getenv("GOOGLE_GENAI_KEY"))
    model = genai.GenerativeModel("gemini-1.5-flash")

    _ = await model.generate_content_async("Explain how AI works in simple terms")

    calls = list(client.calls())
    assert len(calls) == 1

    call = calls[0]
    assert call.started_at < call.ended_at
    trace_name = op_name_from_ref(call.op_name)
    assert trace_name == "google.generativeai.GenerativeModel.generate_content_async"
    assert call.output is not None
    assert_correct_output_shape(call.output)
    assert_correct_summary(call.summary, trace_name)
