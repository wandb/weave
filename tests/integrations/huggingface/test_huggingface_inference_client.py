import os

import pytest

from weave.integrations.integration_utilities import op_name_from_ref


@pytest.mark.skip_clickhouse_client
@pytest.mark.vcr(
    filter_headers=["authorization", "x-api-key"],
    allowed_hosts=["api.wandb.ai", "localhost", "trace.wandb.ai"],
)
def test_huggingface_chat_completion(client):
    from huggingface_hub import InferenceClient

    huggingface_client = InferenceClient(
        api_key=os.environ.get("HUGGINGFACE_API_KEY", "DUMMY_API_KEY")
    )
    image_url = "https://cdn.britannica.com/61/93061-050-99147DCE/Statue-of-Liberty-Island-New-York-Bay.jpg"
    huggingface_client.chat_completion(
        model="meta-llama/Llama-3.2-11B-Vision-Instruct",
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": image_url}},
                    {"type": "text", "text": "Describe this image in one sentence."},
                ],
            }
        ],
        max_tokens=500,
        seed=42,
    )

    calls = list(client.calls())
    assert len(calls) == 1

    call = calls[0]
    assert call.started_at < call.ended_at
    assert (
        op_name_from_ref(call.op_name)
        == "huggingface_hub.InferenceClient.chat_completion"
    )
    output = call.output
    assert output.choices[0].finish_reason == "stop"
    assert output.choices[0].index == 0
    assert "statue of liberty" in output.choices[0].message.content.lower()
    assert output.choices[0].message.role == "assistant"
    assert output.model == "meta-llama/Llama-3.2-11B-Vision-Instruct"
    assert output.usage.prompt_tokens == 44
