import os
import pytest
import weave
from weave.trace_server import trace_server_interface as tsi
from mistralai.client import MistralClient
from mistralai.models.chat_completion import ChatMessage
from .mistral import mistral_patcher

from typing import Generator


@pytest.fixture()
def patch_mistral() -> Generator[None, None, None]:
    mistral_patcher.attempt_patch()
    yield
    mistral_patcher.undo_patch()


@pytest.mark.vcr(
    filter_headers=["authorization"], allowed_hosts=["api.wandb.ai", "localhost"]
)
def test_mistral_quickstart(
    client: weave.weave_client.WeaveClient, patch_mistral: None
) -> None:
    # This is taken directly from https://docs.mistral.ai/getting-started/quickstart/
    api_key = os.environ.get("MISTRAL_API_KEY", "DUMMY_API_KEY")
    model = "mistral-large-latest"

    mistral_client = MistralClient(api_key=api_key)

    chat_response = mistral_client.chat(
        model=model,
        messages=[ChatMessage(role="user", content="What is the best French cheese?")],
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
    # We really should be auto-resolving this for the user...
    output_ref_str = res.calls[0].output
    assert isinstance(output_ref_str, str)
    output = weave.ref(output_ref_str).get()
    assert output.choices[0].message.content == exp
    # Probably should do some other more robust testing here


@pytest.mark.vcr(
    filter_headers=["authorization"], allowed_hosts=["api.wandb.ai", "localhost"]
)
def test_mistral_quickstart_with_stream(
    client: weave.weave_client.WeaveClient, patch_mistral: None
) -> None:
    # This is taken directly from https://docs.mistral.ai/getting-started/quickstart/
    api_key = os.environ.get("MISTRAL_API_KEY", "DUMMY_API_KEY")
    model = "mistral-large-latest"

    mistral_client = MistralClient(api_key=api_key)

    chat_response = mistral_client.chat_stream(
        model=model,
        messages=[ChatMessage(role="user", content="What is the best French cheese?")],
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
    # We really should be auto-resolving this for the user...
    output_ref_str = res.calls[0].output
    assert isinstance(output_ref_str, str)
    output = weave.ref(output_ref_str).get()
    assert output.choices[0].message.content == exp
    # Probably should do some other more robust testing here
