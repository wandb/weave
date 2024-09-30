import os
from typing import Any

import pytest

import weave
from weave.trace_server import trace_server_interface as tsi


def _get_call_output(call: tsi.CallSchema) -> Any:
    """This is a hack and should not be needed. We should be able to auto-resolve this for the user.

    Keeping this here for now, but it should be removed in the future once we have a better solution.
    """
    call_output = call.output
    if isinstance(call_output, str) and call_output.startswith("weave://"):
        return weave.ref(call_output).get()
    return call_output


@pytest.mark.skip_clickhouse_client
@pytest.mark.vcr(
    filter_headers=["authorization"], allowed_hosts=["api.wandb.ai", "localhost"]
)
def test_mistral_quickstart(client: weave.trace.weave_client.WeaveClient) -> None:
    # This is taken directly from https://docs.mistral.ai/getting-started/quickstart/
    from mistralai import Mistral  # type: ignore

    api_key = os.environ.get("MISTRAL_API_KEY", "DUMMY_API_KEY")
    model = "mistral-large-latest"

    mistral_client = Mistral(api_key=api_key)

    chat_response = mistral_client.chat.complete(
        model=model,
        messages=[{"role": "user", "content": "What is the best French cheese?"}],
    )

    all_content = chat_response.choices[0].message.content
    exp = """Choosing the "best" French cheese can be subjective, as it largely depends on personal taste. France is renowned for its wide variety of cheeses, with over 400 different types. Here are a few highly regarded French cheeses across various categories:

1. **Soft Cheeses**:
   - **Brie de Meaux**: Known for its creamy texture and rich, buttery flavor.
   - **Camembert de Normandie**: Soft, creamy, and has a distinctive earthy aroma.

2. **Semi-Soft Cheeses**:
   - **Morbier**: Recognizable by the layer of ash in the middle, it has a fruity and slightly nutty taste.
   - **Reblochon**: A savory cheese from the Alps, often used in tartiflette, a traditional dish.

3. **Hard Cheeses**:
   - **Comté**: A nutty and slightly sweet cheese, similar to Gruyère.
   - **Beaufort**: Known for its firm texture and complex, nutty flavor.

4. **Blue Cheeses**:
   - **Roquefort**: A tangy and pungent blue cheese made from sheep's milk.
   - **Bleu d'Auvergne**: A creamy and strong-flavored blue cheese.

5. **Goat Cheeses**:
   - **Chèvre**: Available in many forms, from fresh and creamy to aged and crumbly.
   - **Crottin de Chavignol**: A small, round goat cheese with a nutty flavor.

Each of these cheeses has its unique characteristics, so the "best" one depends on your preferences. It's always fun to try several and decide which you like the most!"""
    assert all_content == exp
    res = client.server.calls_query(tsi.CallsQueryReq(project_id=client._project_id()))
    assert len(res.calls) == 1
    call = res.calls[0]
    assert call.exception is None and call.ended_at is not None
    output = _get_call_output(call)
    print(f"{output['choices'][0]=}")
    assert output["choices"][0]["message"]["content"] == exp
    assert output["choices"][0]["finish_reason"] == "stop"
    assert output["id"] == chat_response.id
    assert output["model"] == chat_response.model
    assert output["object"] == chat_response.object
    assert output["created"] == chat_response.created
    summary = call.summary
    assert summary is not None
    model_usage = summary["usage"][output["model"]]
    assert model_usage["requests"] == 1
    assert (
        output["usage"]["completion_tokens"] == model_usage["completion_tokens"] == 406
    )
    assert output["usage"]["prompt_tokens"] == model_usage["prompt_tokens"] == 10
    assert output["usage"]["total_tokens"] == model_usage["total_tokens"] == 416


@pytest.mark.skip_clickhouse_client
@pytest.mark.vcr(
    filter_headers=["authorization"], allowed_hosts=["api.wandb.ai", "localhost"]
)
@pytest.mark.asyncio
async def test_mistral_quickstart_async(
    client: weave.trace.weave_client.WeaveClient,
) -> None:
    from mistralai import Mistral  # type: ignore

    # This is taken directly from https://docs.mistral.ai/getting-started/quickstart/
    api_key = os.environ.get("MISTRAL_API_KEY", "DUMMY_API_KEY")
    model = "mistral-large-latest"

    mistral_client = Mistral(api_key=api_key)

    chat_response = await mistral_client.chat.complete_async(
        model=model,
        messages=[{"role": "user", "content": "What is the best French cheese?"}],
    )

    all_content = chat_response.choices[0].message.content
    exp = """Choosing the "best" French cheese is quite subjective and depends on personal taste, as France has a wide variety of excellent cheeses. Here are a few renowned ones that are often considered among the best:

1. **Roquefort**: This is a sheep milk blue cheese from the south of France. It's known for its tangy and salty flavor, and distinctive veins of blue mold.

2. **Camembert de Normandie**: A soft, creamy, surface-ripened cow's milk cheese. It has a rich, buttery flavor and is often enjoyed when fully ripe and gooey.

3. **Brie de Meaux**: Another soft cow's milk cheese, similar to Camembert but slightly milder in flavor. It's known for its edible white rind and creamy interior.

4. **Comté**: A French cheese made from unpasteurized cow's milk in the Franche-Comté region. It has a complex, nutty flavor and a firm, springy texture.

5. **Reblochon**: A soft, washed-rind and smear-ripened cheese made in the Alpine region of Savoy from raw cow's milk. It has a nutty taste and a strong aroma.

6. **Époisses de Bourgogne**: A pungent, washed-rind cheese made from cow's milk. It has a strong, somewhat salty flavor and a sticky, orange exterior.

Each of these cheeses offers a unique taste and texture, so the "best" one is a matter of personal preference."""

    assert all_content == exp
    res = client.server.calls_query(tsi.CallsQueryReq(project_id=client._project_id()))
    assert len(res.calls) == 1
    call = res.calls[0]
    assert call.exception is None and call.ended_at is not None
    output = _get_call_output(call)
    assert output["choices"][0]["message"]["content"] == exp
    assert output["choices"][0]["finish_reason"] == "stop"
    assert output["id"] == chat_response.id
    assert output["model"] == chat_response.model
    assert output["object"] == chat_response.object
    assert output["created"] == chat_response.created
    summary = call.summary
    assert summary is not None
    model_usage = summary["usage"][output["model"]]
    assert model_usage["requests"] == 1
    assert (
        output["usage"]["completion_tokens"] == model_usage["completion_tokens"] == 363
    )
    assert output["usage"]["prompt_tokens"] == model_usage["prompt_tokens"] == 10
    assert output["usage"]["total_tokens"] == model_usage["total_tokens"] == 373


@pytest.mark.skip_clickhouse_client
@pytest.mark.vcr(
    filter_headers=["authorization"], allowed_hosts=["api.wandb.ai", "localhost"]
)
def test_mistral_quickstart_with_stream(
    client: weave.trace.weave_client.WeaveClient,
) -> None:
    from mistralai import Mistral  # type: ignore

    # This is taken directly from https://docs.mistral.ai/getting-started/quickstart/
    api_key = os.environ.get("MISTRAL_API_KEY", "DUMMY_API_KEY")
    model = "mistral-large-latest"

    mistral_client = Mistral(api_key=api_key)

    chat_response = mistral_client.chat.stream(
        model=model,
        messages=[{"role": "user", "content": "What is the best French cheese?"}],
    )

    all_content = ""
    for chunk in chat_response:
        all_content += chunk.data.choices[0].delta.content

    exp = """Choosing the "best" French cheese can be subjective as it depends on personal taste, but France is renowned for its wide variety of high-quality cheeses. Here are a few that are often highly regarded:

1. **Roquefort**: A sheep milk blue cheese from the south of France, known for its tangy, salty flavor and distinctive veins of blue mold.

2. **Brie de Meaux**: A soft, creamy cow's milk cheese from the Île-de-France region. It has a rich, buttery flavor and is often considered one of the finest cheeses in the world.

3. **Camembert de Normandie**: A soft, creamy cow's milk cheese from Normandy, similar to Brie but with a slightly stronger flavor.

4. **Comté**: A hard, unpasteurized cow's milk cheese from the Jura Massif region. It has a complex, nutty flavor that varies depending on its age.

5. **Époisses de Bourgogne**: A pungent, soft cow's milk cheese from Burgundy, often served with a spoon due to its runny texture.

6. **Morbier**: A semi-soft cow's milk cheese with a distinctive layer of ash in the middle. It has a rich, creamy flavor with a slight bitterness.

Each of these cheeses offers a unique taste and texture, so the "best" one depends on your personal preference. It's always fun to try a variety to see which you like best!"""
    assert all_content == exp
    res = client.server.calls_query(tsi.CallsQueryReq(project_id=client._project_id()))
    assert len(res.calls) == 1
    call = res.calls[0]
    assert call.exception is None and call.ended_at is not None
    output = _get_call_output(call)
    print(f"{output=}")
    assert output["choices"][0]["message"]["content"] == exp
    assert output["choices"][0]["finish_reason"] == "stop"
    assert output["id"] == chunk.data.id
    assert output["model"] == chunk.data.model
    assert output["object"] == chunk.data.object
    assert output["created"] == chunk.data.created
    summary = call.summary
    assert summary is not None
    model_usage = summary["usage"][output["model"]]
    assert model_usage["requests"] == 1
    assert (
        output["usage"]["completion_tokens"] == model_usage["completion_tokens"] == 350
    )
    assert output["usage"]["prompt_tokens"] == model_usage["prompt_tokens"] == 10
    assert output["usage"]["total_tokens"] == model_usage["total_tokens"] == 360


@pytest.mark.skip_clickhouse_client
@pytest.mark.vcr(
    filter_headers=["authorization"], allowed_hosts=["api.wandb.ai", "localhost"]
)
@pytest.mark.asyncio
async def test_mistral_quickstart_with_stream_async(
    client: weave.trace.weave_client.WeaveClient,
) -> None:
    from mistralai import Mistral  # type: ignore

    # This is taken directly from https://docs.mistral.ai/getting-started/quickstart/
    api_key = os.environ.get("MISTRAL_API_KEY", "DUMMY_API_KEY")
    model = "mistral-large-latest"

    mistral_client = Mistral(api_key=api_key)

    chat_response = await mistral_client.chat.stream_async(
        model=model,
        messages=[{"role": "user", "content": "What is the best French cheese?"}],
    )

    all_content = ""
    async for chunk in chat_response:
        all_content += chunk.data.choices[0].delta.content

    exp = """Choosing the "best" French cheese can be subjective as it largely depends on personal taste. France is renowned for its wide variety of cheeses, with over 400 different types. Here are a few highly regarded French cheeses across various categories:

1. **Soft Cheeses**:
   - **Brie de Meaux**: Known for its rich, creamy texture and earthy, mushroom-like flavor.
   - **Camembert de Normandie**: Soft, creamy, and has a strong, distinctive smell.

2. **Semi-Soft Cheeses**:
   - **Morbier**: Recognizable by its layer of ash in the middle, it has a fruity and slightly nutty taste.
   - **Reblochon**: A savory cheese from the Alps with a nutty aftertaste and a soft, washed rind.

3. **Hard Cheeses**:
   - **Comté**: A fruity and nutty cheese made from unpasteurized cow's milk, often aged for many months.
   - **Beaufort**: Similar to Gruyère, it has a firm texture and a sweet, nutty flavor.

4. **Blue Cheeses**:
   - **Roquefort**: A sheep milk cheese with distinctive veins of blue mold, offering a tangy and salty taste.
   - **Bleu d'Auvergne**: A cow's milk blue cheese with a strong, pungent aroma and a creamy texture.

5. **Goat Cheeses**:
   - **Chèvre**: Available in many forms, from fresh and creamy to aged and crumbly, often with a tangy, earthy flavor.
   - **Crottin de Chavignol**: A small, round goat cheese with a nutty flavor and a texture that varies with age.

Each of these cheeses has its unique characteristics, so the "best" one depends on your preferences. It's always fun to try several types to discover your favorite!"""
    assert all_content == exp
    res = client.server.calls_query(tsi.CallsQueryReq(project_id=client._project_id()))
    assert len(res.calls) == 1
    call = res.calls[0]
    assert call.exception is None and call.ended_at is not None
    output = _get_call_output(call)
    assert output["choices"][0]["message"]["content"] == exp
    assert output["choices"][0]["finish_reason"] == "stop"
    assert output["id"] == chunk.data.id
    assert output["model"] == chunk.data.model
    assert output["object"] == chunk.data.object
    assert output["created"] == chunk.data.created
    summary = call.summary
    assert summary is not None
    model_usage = summary["usage"][output["model"]]
    assert model_usage["requests"] == 1
    assert (
        output["usage"]["completion_tokens"] == model_usage["completion_tokens"] == 459
    )
    assert output["usage"]["prompt_tokens"] == model_usage["prompt_tokens"] == 10
    assert output["usage"]["total_tokens"] == model_usage["total_tokens"] == 469
