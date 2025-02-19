import asyncio
import os

import pytest

from weave.integrations.integration_utilities import op_name_from_ref


@pytest.mark.flaky(reruns=5, reruns_delay=2)
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


@pytest.mark.flaky(reruns=5, reruns_delay=2)
@pytest.mark.skip_clickhouse_client
@pytest.mark.vcr(
    filter_headers=["authorization", "x-api-key"],
    allowed_hosts=["api.wandb.ai", "localhost", "trace.wandb.ai"],
)
def test_huggingface_chat_completion_stream(client):
    from huggingface_hub import InferenceClient

    huggingface_client = InferenceClient(
        api_key=os.environ.get("HUGGINGFACE_API_KEY", "DUMMY_API_KEY")
    )
    image_url = "https://cdn.britannica.com/61/93061-050-99147DCE/Statue-of-Liberty-Island-New-York-Bay.jpg"
    result = huggingface_client.chat_completion(
        model="meta-llama/Llama-3.2-11B-Vision-Instruct",
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": image_url}},
                    {
                        "type": "text",
                        "text": "Describe this image in one sentence.",
                    },
                ],
            }
        ],
        max_tokens=500,
        seed=42,
        stream=True,
    )
    chunks = []
    for chunk in result:
        chunks.append(chunk)
    assert len(chunks) > 0
    calls = list(client.calls())
    assert len(calls) == 1

    call = calls[0]
    assert call.started_at < call.ended_at
    assert (
        op_name_from_ref(call.op_name)
        == "huggingface_hub.InferenceClient.chat_completion"
    )
    output = call.output
    assert output.choices[0].index == 0
    assert "statue of liberty" in output.choices[0].message.content.lower()
    assert output.choices[0].message.role == "assistant"
    assert output.model == "meta-llama/Llama-3.2-11B-Vision-Instruct"


@pytest.mark.flaky(reruns=5, reruns_delay=2)
@pytest.mark.skip_clickhouse_client
@pytest.mark.vcr(
    filter_headers=["authorization", "x-api-key"],
    allowed_hosts=["api.wandb.ai", "localhost", "trace.wandb.ai"],
)
def test_huggingface_chat_completion_async(client):
    from huggingface_hub import AsyncInferenceClient

    huggingface_client = AsyncInferenceClient(
        api_key=os.environ.get("HUGGINGFACE_API_KEY", "DUMMY_API_KEY")
    )
    image_url = "https://cdn.britannica.com/61/93061-050-99147DCE/Statue-of-Liberty-Island-New-York-Bay.jpg"
    asyncio.run(
        huggingface_client.chat_completion(
            model="meta-llama/Llama-3.2-11B-Vision-Instruct",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "image_url", "image_url": {"url": image_url}},
                        {
                            "type": "text",
                            "text": "Describe this image in one sentence.",
                        },
                    ],
                }
            ],
            max_tokens=500,
            seed=42,
        )
    )

    calls = list(client.calls())
    assert len(calls) == 1

    call = calls[0]
    assert call.started_at < call.ended_at
    assert (
        op_name_from_ref(call.op_name)
        == "huggingface_hub.AsyncInferenceClient.chat_completion"
    )
    output = call.output
    assert output.choices[0].finish_reason == "stop"
    assert output.choices[0].index == 0
    assert "statue of liberty" in output.choices[0].message.content.lower()
    assert output.choices[0].message.role == "assistant"
    assert output.model == "meta-llama/Llama-3.2-11B-Vision-Instruct"
    assert output.usage.prompt_tokens == 44


@pytest.mark.skip(reason="This test depends on a huggingface model endpoint that does not reliably work.")
@pytest.mark.flaky(reruns=5, reruns_delay=2)
@pytest.mark.skip_clickhouse_client
@pytest.mark.vcr(
    filter_headers=["authorization", "x-api-key"],
    allowed_hosts=["api.wandb.ai", "localhost", "trace.wandb.ai"],
)
def test_huggingface_document_question_answering(client):
    from huggingface_hub import InferenceClient

    image_url = "https://huggingface.co/spaces/impira/docquery/resolve/2359223c1837a7587402bda0f2643382a6eefeab/invoice.png"
    InferenceClient(
        api_key=os.environ.get("HUGGINGFACE_API_KEY", "DUMMY_API_KEY")
    ).document_question_answering(
        image=image_url,
        model="impira/layoutlm-document-qa",
        question="What is the invoice number?",
    )

    calls = list(client.calls())
    assert len(calls) == 1

    call = calls[0]
    assert call.started_at < call.ended_at
    assert (
        op_name_from_ref(call.op_name)
        == "huggingface_hub.InferenceClient.document_question_answering"
    )
    output = call.output
    assert output[0].answer == "us-001"


@pytest.mark.skip(reason="This test depends on a huggingface model endpoint that does not reliably work.")
@pytest.mark.flaky(reruns=5, reruns_delay=2)
@pytest.mark.skip_clickhouse_client
@pytest.mark.vcr(
    filter_headers=["authorization", "x-api-key"],
    allowed_hosts=["api.wandb.ai", "localhost", "trace.wandb.ai"],
)
def test_huggingface_document_question_answering_async(client):
    from huggingface_hub import AsyncInferenceClient

    image_url = "https://huggingface.co/spaces/impira/docquery/resolve/2359223c1837a7587402bda0f2643382a6eefeab/invoice.png"
    asyncio.run(
        AsyncInferenceClient(
            api_key=os.environ.get("HUGGINGFACE_API_KEY", "DUMMY_API_KEY")
        ).document_question_answering(
            image=image_url,
            model="impira/layoutlm-document-qa",
            question="What is the invoice number?",
        )
    )

    calls = list(client.calls())
    assert len(calls) == 1

    call = calls[0]
    assert call.started_at < call.ended_at
    assert (
        op_name_from_ref(call.op_name)
        == "huggingface_hub.AsyncInferenceClient.document_question_answering"
    )
    output = call.output
    assert output[0].answer == "us-001"


@pytest.mark.skip(reason="This test depends on a huggingface model endpoint that does not reliably work.")
@pytest.mark.flaky(reruns=5, reruns_delay=2)
@pytest.mark.skip_clickhouse_client
@pytest.mark.vcr(
    filter_headers=["authorization", "x-api-key"],
    allowed_hosts=["api.wandb.ai", "localhost", "trace.wandb.ai"],
)
def test_huggingface_fill_mask(client):
    from huggingface_hub import InferenceClient

    InferenceClient(
        api_key=os.getenv("HUGGINGFACE_API_KEY", "DUMMY_API_KEY")
    ).fill_mask("The goal of life is <mask>.")

    calls = list(client.calls())
    assert len(calls) == 1

    call = calls[0]
    assert call.started_at < call.ended_at
    assert op_name_from_ref(call.op_name) == "huggingface_hub.InferenceClient.fill_mask"
    output = call.output
    assert output[0].token_str in output[0].sequence
    assert output[0].score > 0


@pytest.mark.skip(reason="This test depends on a huggingface model endpoint that does not reliably work.")
@pytest.mark.flaky(reruns=5, reruns_delay=2)
@pytest.mark.skip_clickhouse_client
@pytest.mark.vcr(
    filter_headers=["authorization", "x-api-key"],
    allowed_hosts=["api.wandb.ai", "localhost", "trace.wandb.ai"],
)
def test_huggingface_fill_mask_async(client):
    from huggingface_hub import AsyncInferenceClient

    asyncio.run(
        AsyncInferenceClient(
            api_key=os.getenv("HUGGINGFACE_API_KEY", "DUMMY_API_KEY")
        ).fill_mask("The goal of life is <mask>.")
    )

    calls = list(client.calls())
    assert len(calls) == 1

    call = calls[0]
    assert call.started_at < call.ended_at
    assert (
        op_name_from_ref(call.op_name)
        == "huggingface_hub.AsyncInferenceClient.fill_mask"
    )
    output = call.output
    assert output[0].token_str in output[0].sequence
    assert output[0].score > 0


@pytest.mark.flaky(reruns=5, reruns_delay=2)
@pytest.mark.skip_clickhouse_client
@pytest.mark.vcr(
    filter_headers=["authorization", "x-api-key"],
    allowed_hosts=["api.wandb.ai", "localhost", "trace.wandb.ai"],
)
def test_huggingface_question_answering(client):
    from huggingface_hub import InferenceClient

    InferenceClient(
        api_key=os.getenv("HUGGINGFACE_API_KEY", "DUMMY_API_KEY")
    ).question_answering(
        question="What's my name?", context="My name is Clara and I live in Berkeley."
    )

    calls = list(client.calls())
    assert len(calls) == 1

    call = calls[0]
    assert call.started_at < call.ended_at
    assert (
        op_name_from_ref(call.op_name)
        == "huggingface_hub.InferenceClient.question_answering"
    )
    output = call.output
    assert output.answer == "Clara"


@pytest.mark.flaky(reruns=5, reruns_delay=2)
@pytest.mark.skip_clickhouse_client
@pytest.mark.vcr(
    filter_headers=["authorization", "x-api-key"],
    allowed_hosts=["api.wandb.ai", "localhost", "trace.wandb.ai"],
)
def test_huggingface_question_answering_async(client):
    from huggingface_hub import AsyncInferenceClient

    asyncio.run(
        AsyncInferenceClient(
            api_key=os.getenv("HUGGINGFACE_API_KEY", "DUMMY_API_KEY")
        ).question_answering(
            question="What's my name?",
            context="My name is Clara and I live in Berkeley.",
        )
    )

    calls = list(client.calls())
    assert len(calls) == 1

    call = calls[0]
    assert call.started_at < call.ended_at
    assert (
        op_name_from_ref(call.op_name)
        == "huggingface_hub.AsyncInferenceClient.question_answering"
    )
    output = call.output
    assert output.answer == "Clara"


@pytest.mark.skip(reason="This test depends on a huggingface model endpoint that does not reliably work.")
@pytest.mark.flaky(reruns=5, reruns_delay=2)
@pytest.mark.skip_clickhouse_client
@pytest.mark.vcr(
    filter_headers=["authorization", "x-api-key"],
    allowed_hosts=["api.wandb.ai", "localhost", "trace.wandb.ai"],
)
def test_huggingface_table_question_answering(client):
    from huggingface_hub import InferenceClient

    query = "How many stars does the transformers repository have?"
    table = {
        "Repository": ["Transformers", "Datasets", "Tokenizers"],
        "Stars": ["36542", "4512", "3934"],
    }
    InferenceClient(
        api_key=os.getenv("HUGGINGFACE_API_KEY", "DUMMY_API_KEY")
    ).table_question_answering(table, query, model="google/tapas-base-finetuned-wtq")

    calls = list(client.calls())
    assert len(calls) == 1

    call = calls[0]
    assert call.started_at < call.ended_at
    assert (
        op_name_from_ref(call.op_name)
        == "huggingface_hub.InferenceClient.table_question_answering"
    )
    output = call.output
    assert output.answer == "AVERAGE > 36542"


@pytest.mark.skip(reason="This test depends on a huggingface model endpoint that does not reliably work.")
@pytest.mark.flaky(reruns=5, reruns_delay=2)
@pytest.mark.skip_clickhouse_client
@pytest.mark.vcr(
    filter_headers=["authorization", "x-api-key"],
    allowed_hosts=["api.wandb.ai", "localhost", "trace.wandb.ai"],
)
def test_huggingface_table_question_answering_async(client):
    from huggingface_hub import AsyncInferenceClient

    query = "How many stars does the transformers repository have?"
    table = {
        "Repository": ["Transformers", "Datasets", "Tokenizers"],
        "Stars": ["36542", "4512", "3934"],
    }
    asyncio.run(
        AsyncInferenceClient(
            api_key=os.getenv("HUGGINGFACE_API_KEY", "DUMMY_API_KEY")
        ).table_question_answering(
            table, query, model="google/tapas-base-finetuned-wtq"
        )
    )

    calls = list(client.calls())
    assert len(calls) == 1

    call = calls[0]
    assert call.started_at < call.ended_at
    assert (
        op_name_from_ref(call.op_name)
        == "huggingface_hub.AsyncInferenceClient.table_question_answering"
    )
    output = call.output
    assert output.answer == "AVERAGE > 36542"


@pytest.mark.flaky(reruns=5, reruns_delay=2)
@pytest.mark.skip_clickhouse_client
@pytest.mark.vcr(
    filter_headers=["authorization", "x-api-key"],
    allowed_hosts=["api.wandb.ai", "localhost", "trace.wandb.ai"],
)
def test_huggingface_text_classification(client):
    from huggingface_hub import InferenceClient

    InferenceClient(
        api_key=os.getenv("HUGGINGFACE_API_KEY", "DUMMY_API_KEY")
    ).text_classification("I like you")

    calls = list(client.calls())
    assert len(calls) == 1

    call = calls[0]
    assert call.started_at < call.ended_at
    assert (
        op_name_from_ref(call.op_name)
        == "huggingface_hub.InferenceClient.text_classification"
    )
    output = call.output
    assert output[0].label == "POSITIVE"
    assert output[0].score > 0


@pytest.mark.flaky(reruns=5, reruns_delay=2)
@pytest.mark.skip_clickhouse_client
@pytest.mark.vcr(
    filter_headers=["authorization", "x-api-key"],
    allowed_hosts=["api.wandb.ai", "localhost", "trace.wandb.ai"],
)
def test_huggingface_text_classification_async(client):
    from huggingface_hub import AsyncInferenceClient

    asyncio.run(
        AsyncInferenceClient(
            api_key=os.getenv("HUGGINGFACE_API_KEY", "DUMMY_API_KEY")
        ).text_classification("I like you")
    )

    calls = list(client.calls())
    assert len(calls) == 1

    call = calls[0]
    assert call.started_at < call.ended_at
    assert (
        op_name_from_ref(call.op_name)
        == "huggingface_hub.AsyncInferenceClient.text_classification"
    )
    output = call.output
    assert output[0].label == "POSITIVE"
    assert output[0].score > 0


@pytest.mark.skip(reason="This test depends on a huggingface model endpoint that does not reliably work.")
@pytest.mark.flaky(reruns=5, reruns_delay=2)
@pytest.mark.skip_clickhouse_client
@pytest.mark.vcr(
    filter_headers=["authorization", "x-api-key"],
    allowed_hosts=["api.wandb.ai", "localhost", "trace.wandb.ai"],
)
def test_huggingface_token_classification(client):
    from huggingface_hub import InferenceClient

    InferenceClient(
        api_key=os.getenv("HUGGINGFACE_API_KEY", "DUMMY_API_KEY")
    ).token_classification(
        "My name is Sarah Jessica Parker but you can call me Jessica"
    )

    calls = list(client.calls())
    assert len(calls) == 1

    call = calls[0]
    assert call.started_at < call.ended_at
    assert (
        op_name_from_ref(call.op_name)
        == "huggingface_hub.InferenceClient.token_classification"
    )
    output = call.output
    assert output[0].word == "Sarah Jessica Parker"
    assert output[0].score > 0


@pytest.mark.skip(reason="This test depends on a huggingface model endpoint that does not reliably work.")
@pytest.mark.flaky(reruns=5, reruns_delay=2)
@pytest.mark.skip_clickhouse_client
@pytest.mark.vcr(
    filter_headers=["authorization", "x-api-key"],
    allowed_hosts=["api.wandb.ai", "localhost", "trace.wandb.ai"],
)
def test_huggingface_token_classification_async(client):
    from huggingface_hub import AsyncInferenceClient

    asyncio.run(
        AsyncInferenceClient(
            api_key=os.getenv("HUGGINGFACE_API_KEY", "DUMMY_API_KEY")
        ).token_classification(
            "My name is Sarah Jessica Parker but you can call me Jessica"
        )
    )

    calls = list(client.calls())
    assert len(calls) == 1

    call = calls[0]
    assert call.started_at < call.ended_at
    assert (
        op_name_from_ref(call.op_name)
        == "huggingface_hub.AsyncInferenceClient.token_classification"
    )
    output = call.output
    assert output[0].word == "Sarah Jessica Parker"
    assert output[0].score > 0


@pytest.mark.flaky(reruns=5, reruns_delay=2)
@pytest.mark.skip_clickhouse_client
@pytest.mark.vcr(
    filter_headers=["authorization", "x-api-key"],
    allowed_hosts=["api.wandb.ai", "localhost", "trace.wandb.ai"],
)
def test_huggingface_translation(client):
    from huggingface_hub import InferenceClient

    InferenceClient(
        api_key=os.getenv("HUGGINGFACE_API_KEY", "DUMMY_API_KEY")
    ).translation(
        "My name is Wolfgang and I live in Berlin", model="Helsinki-NLP/opus-mt-en-fr"
    )

    calls = list(client.calls())
    assert len(calls) == 1

    call = calls[0]
    assert call.started_at < call.ended_at
    assert (
        op_name_from_ref(call.op_name) == "huggingface_hub.InferenceClient.translation"
    )
    output = call.output
    assert "Wolfgang" in output.translation_text


@pytest.mark.flaky(reruns=5, reruns_delay=2)
@pytest.mark.skip_clickhouse_client
@pytest.mark.vcr(
    filter_headers=["authorization", "x-api-key"],
    allowed_hosts=["api.wandb.ai", "localhost", "trace.wandb.ai"],
)
def test_huggingface_translation_async(client):
    from huggingface_hub import AsyncInferenceClient

    asyncio.run(
        AsyncInferenceClient(
            api_key=os.getenv("HUGGINGFACE_API_KEY", "DUMMY_API_KEY")
        ).translation(
            "My name is Wolfgang and I live in Berlin",
            model="Helsinki-NLP/opus-mt-en-fr",
        )
    )

    calls = list(client.calls())
    assert len(calls) == 1

    call = calls[0]
    assert call.started_at < call.ended_at
    assert (
        op_name_from_ref(call.op_name)
        == "huggingface_hub.AsyncInferenceClient.translation"
    )
    output = call.output
    assert "Wolfgang" in output.translation_text


@pytest.mark.flaky(reruns=5, reruns_delay=2)
@pytest.mark.skip_clickhouse_client
@pytest.mark.vcr(
    filter_headers=["authorization", "x-api-key"],
    allowed_hosts=["api.wandb.ai", "localhost", "trace.wandb.ai"],
)
def test_huggingface_text_to_image(client):
    from huggingface_hub import InferenceClient

    InferenceClient(
        api_key=os.getenv("HUGGINGFACE_API_KEY", "DUMMY_API_KEY")
    ).text_to_image(
        prompt="A cute puppy",
        model="black-forest-labs/FLUX.1-schnell",
        num_inference_steps=4,
    )

    calls = list(client.calls())
    assert len(calls) == 1

    call = calls[0]
    assert call.started_at < call.ended_at
    assert (
        op_name_from_ref(call.op_name)
        == "huggingface_hub.InferenceClient.text_to_image"
    )
    output = call.output
    assert output is not None


@pytest.mark.flaky(reruns=5, reruns_delay=2)
@pytest.mark.skip_clickhouse_client
@pytest.mark.vcr(
    filter_headers=["authorization", "x-api-key"],
    allowed_hosts=["api.wandb.ai", "localhost", "trace.wandb.ai"],
)
def test_huggingface_text_to_image_async(client):
    from huggingface_hub import AsyncInferenceClient

    asyncio.run(
        AsyncInferenceClient(
            api_key=os.getenv("HUGGINGFACE_API_KEY", "DUMMY_API_KEY")
        ).text_to_image(
            prompt="A cute puppy",
            model="black-forest-labs/FLUX.1-schnell",
            num_inference_steps=4,
        )
    )

    calls = list(client.calls())
    assert len(calls) == 1

    call = calls[0]
    assert call.started_at < call.ended_at
    assert (
        op_name_from_ref(call.op_name)
        == "huggingface_hub.AsyncInferenceClient.text_to_image"
    )
    output = call.output
    assert output is not None
