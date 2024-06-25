import os
from typing import Any, Generator

import pytest
from mistralai.async_client import MistralAsyncClient
from mistralai.client import MistralClient

import weave
from weave.trace_server import trace_server_interface as tsi

from .mistral import mistral_patcher


def _get_call_output(call: tsi.CallSchema) -> Any:
    """This is a hack and should not be needed. We should be able to auto-resolve this for the user.

    Keeping this here for now, but it should be removed in the future once we have a better solution.
    """
    call_output = call.output
    if isinstance(call_output, str) and call_output.startswith("weave://"):
        return weave.ref(call_output).get()
    return call_output


@pytest.mark.skip_clickhouse_client  # TODO:VCR recording does not seem to allow us to make requests to the clickhouse db in non-recording mode
@pytest.mark.vcr(
    filter_headers=["authorization"], allowed_hosts=["api.wandb.ai", "localhost"]
)
def test_mistral_quickstart(client: weave.weave_client.WeaveClient) -> None:
    # This is taken directly from https://docs.mistral.ai/getting-started/quickstart/
    api_key = os.environ.get("MISTRAL_API_KEY", "DUMMY_API_KEY")
    model = "mistral-large-latest"

    mistral_client = MistralClient(api_key=api_key)

    chat_response = mistral_client.chat(
        model=model,
        messages=[dict(role="user", content="What is the best French cheese?")],
    )

    all_content = chat_response.choices[0].message.content
    exp = """The "best" French cheese can vary greatly depending on personal preferences, as there are hundreds of different types of French cheeses, each with its unique flavor, texture, and aroma. However, some French cheeses are particularly popular and renowned:

1. Brie de Meaux: Often simply called Brie, this is a soft cheese with a white rind and a creamy, rich interior. It's one of the most well-known French cheeses internationally.

2. Camembert: Similar to Brie, Camembert is a soft, surface-ripened cheese. It has a stronger flavor and aroma compared to Brie.

3. Roquefort: This is a blue cheese made from sheep's milk. It's tangy, sharp, and slightly salty.

4. Comté: A hard cheese made from unpasteurized cow's milk, Comté has a nutty, slightly sweet flavor.

5. Reblochon: This is a soft, rind-washed cheese with a nutty and fruity taste. It's often used in tartiflette, a classic French dish from the Savoie region.

6. Époisses: Known for its pungent smell, Époisses is a soft, washed-rind cheese with a rich and creamy flavor."""

    assert all_content == exp
    res = client.server.calls_query(tsi.CallsQueryReq(project_id=client._project_id()))
    assert len(res.calls) == 1
    call = res.calls[0]
    assert call.exception is None and call.ended_at is not None
    output = _get_call_output(call)
    assert output.choices[0].message.content == exp
    assert output.choices[0].finish_reason == "stop"
    assert output.id == chat_response.id
    assert output.model == chat_response.model
    assert output.object == chat_response.object
    assert output.created == chat_response.created
    summary = call.summary
    assert summary is not None
    model_usage = summary["usage"][output.model]
    assert model_usage["requests"] == 1
    assert output.usage.completion_tokens == model_usage["completion_tokens"] == 299
    assert output.usage.prompt_tokens == model_usage["prompt_tokens"] == 10
    assert output.usage.total_tokens == model_usage["total_tokens"] == 309


@pytest.mark.skip_clickhouse_client  # TODO:VCR recording does not seem to allow us to make requests to the clickhouse db in non-recording mode
@pytest.mark.vcr(
    filter_headers=["authorization"], allowed_hosts=["api.wandb.ai", "localhost"]
)
@pytest.mark.asyncio
async def test_mistral_quickstart_async(client: weave.weave_client.WeaveClient) -> None:
    # This is taken directly from https://docs.mistral.ai/getting-started/quickstart/
    api_key = os.environ.get("MISTRAL_API_KEY", "DUMMY_API_KEY")
    model = "mistral-large-latest"

    mistral_client = MistralAsyncClient(api_key=api_key)

    chat_response = await mistral_client.chat(
        model=model,
        messages=[dict(role="user", content="What is the best French cheese?")],
    )

    all_content = chat_response.choices[0].message.content
    exp = """There are many excellent French cheeses, and the "best" one often depends on personal preference. However, some of the most popular and highly regarded French cheeses include:

* Comté: A hard cheese made from unpasteurized cow's milk in the Franche-Comté region of eastern France. It has a rich, nutty flavor and a firm, slightly granular texture.
* Camembert: A soft, surface-ripened cheese made from cow's milk in Normandy. It has a bloomy white rind and a creamy, earthy flavor.
* Roquefort: A blue cheese made from sheep's milk in the south of France. It has a tangy, slightly salty flavor and a crumbly texture.
* Brie: A soft cheese made from cow's milk in the Île-de-France region around Paris. It has a white, edible rind and a creamy, buttery flavor.
* Reblochon: A soft, washed-rind cheese made from cow's milk in the Savoie region of the French Alps. It has a nutty, fruity flavor and a soft, supple texture.

Ultimately, the best French cheese is a matter of personal taste. I would recommend trying a variety of cheeses and seeing which ones you enjoy the most."""

    assert all_content == exp
    res = client.server.calls_query(tsi.CallsQueryReq(project_id=client._project_id()))
    assert len(res.calls) == 1
    call = res.calls[0]
    assert call.exception is None and call.ended_at is not None
    output = _get_call_output(call)
    assert output.choices[0].message.content == exp
    assert output.choices[0].finish_reason == "stop"
    assert output.id == chat_response.id
    assert output.model == chat_response.model
    assert output.object == chat_response.object
    assert output.created == chat_response.created
    summary = call.summary
    assert summary is not None
    model_usage = summary["usage"][output.model]
    assert model_usage["requests"] == 1
    assert output.usage.completion_tokens == model_usage["completion_tokens"] == 297
    assert output.usage.prompt_tokens == model_usage["prompt_tokens"] == 10
    assert output.usage.total_tokens == model_usage["total_tokens"] == 307


@pytest.mark.skip_clickhouse_client  # TODO:VCR recording does not seem to allow us to make requests to the clickhouse db in non-recording mode
@pytest.mark.vcr(
    filter_headers=["authorization"], allowed_hosts=["api.wandb.ai", "localhost"]
)
def test_mistral_quickstart_with_stream(client: weave.weave_client.WeaveClient) -> None:
    # This is taken directly from https://docs.mistral.ai/getting-started/quickstart/
    api_key = os.environ.get("MISTRAL_API_KEY", "DUMMY_API_KEY")
    model = "mistral-large-latest"

    mistral_client = MistralClient(api_key=api_key)

    chat_response = mistral_client.chat_stream(
        model=model,
        messages=[dict(role="user", content="What is the best French cheese?")],
    )

    all_content = ""
    for chunk in chat_response:
        all_content += chunk.choices[0].delta.content

    exp = """France is known for its diverse and high-quality cheeses, so the "best" French cheese can depend on personal preference. However, some of the most renowned French cheeses include:

1. Comté: A hard cheese made from unpasteurized cow's milk in the Franche-Comté region. It has a nutty, slightly sweet flavor.

2. Brie de Meaux: Often simply called Brie, this is a soft cheese with a white rind. It's known for its creamy texture and mild, slightly tangy flavor.

3. Roquefort: This is a blue cheese made from sheep's milk. It has a strong, tangy flavor and a crumbly texture.

4. Camembert: Similar to Brie, Camembert is a soft cheese with a white rind. However, it has a stronger, more earthy flavor.

5. Reblochon: A soft cheese from the Savoie region, it's known for its fruity and nutty taste with a slight bitterness.

6. Époisses: This is a pungent soft cheese with a distinctive orange rind. It's known for its strong flavor and creamy texture."""

    assert all_content == exp
    res = client.server.calls_query(tsi.CallsQueryReq(project_id=client._project_id()))
    assert len(res.calls) == 1
    call = res.calls[0]
    assert call.exception is None and call.ended_at is not None
    output = _get_call_output(call)
    assert output.choices[0].message.content == exp
    assert output.choices[0].finish_reason == "stop"
    assert output.id == chunk.id
    assert output.model == chunk.model
    assert output.object == chunk.object
    assert output.created == chunk.created
    summary = call.summary
    assert summary is not None
    model_usage = summary["usage"][output.model]
    assert model_usage["requests"] == 1
    assert output.usage.completion_tokens == model_usage["completion_tokens"] == 274
    assert output.usage.prompt_tokens == model_usage["prompt_tokens"] == 10
    assert output.usage.total_tokens == model_usage["total_tokens"] == 284


@pytest.mark.skip_clickhouse_client  # TODO:VCR recording does not seem to allow us to make requests to the clickhouse db in non-recording mode
@pytest.mark.vcr(
    filter_headers=["authorization"], allowed_hosts=["api.wandb.ai", "localhost"]
)
@pytest.mark.asyncio
async def test_mistral_quickstart_with_stream_async(
    client: weave.weave_client.WeaveClient,
) -> None:
    # This is taken directly from https://docs.mistral.ai/getting-started/quickstart/
    api_key = os.environ.get("MISTRAL_API_KEY", "DUMMY_API_KEY")
    model = "mistral-large-latest"

    mistral_client = MistralAsyncClient(api_key=api_key)

    chat_response = mistral_client.chat_stream(
        model=model,
        messages=[dict(role="user", content="What is the best French cheese?")],
    )

    all_content = ""
    async for chunk in chat_response:
        all_content += chunk.choices[0].delta.content

    exp = """The "best" French cheese can depend on personal preferences, but here are a few popular ones:

1. Brie: Often referred to as "The Queen of Cheeses," Brie is a soft cheese named after the French region Brie. It has a mild, slightly sweet flavor with a creamy texture.

2. Camembert: This is another soft cheese from Normandy, France. It has a stronger flavor than Brie, with a hint of mushroom taste.

3. Roquefort: This is a blue cheese made from sheep's milk. It's aged in the natural Combalou caves of Roquefort-sur-Soulzon, which gives it a unique, tangy flavor.

4. Comté: This is a hard cheese made from unpasteurized cow's milk in the Franche-Comté region of eastern France. It has a complex, nutty flavor.

5. Chèvre: This is a general term for goat cheese in French. It can come in many forms and flavors, from fresh and mild to aged and tangy."""

    assert all_content == exp
    res = client.server.calls_query(tsi.CallsQueryReq(project_id=client._project_id()))
    assert len(res.calls) == 1
    call = res.calls[0]
    assert call.exception is None and call.ended_at is not None
    output = _get_call_output(call)
    assert output.choices[0].message.content == exp
    assert output.choices[0].finish_reason == "stop"
    assert output.id == chunk.id
    assert output.model == chunk.model
    assert output.object == chunk.object
    assert output.created == chunk.created
    summary = call.summary
    assert summary is not None
    model_usage = summary["usage"][output.model]
    assert model_usage["requests"] == 1
    assert output.usage.completion_tokens == model_usage["completion_tokens"] == 242
    assert output.usage.prompt_tokens == model_usage["prompt_tokens"] == 10
    assert output.usage.total_tokens == model_usage["total_tokens"] == 252
