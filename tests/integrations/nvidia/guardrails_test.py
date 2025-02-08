from typing import Generator
import pytest
import weave
from weave.integrations.nvidia.guardrails import get_nvidia_guardrails_patcher

@pytest.fixture()
def patch_guardrails() -> Generator[None, None, None]:
    get_nvidia_guardrails_patcher().attempt_patch()
    yield
    get_nvidia_guardrails_patcher().undo_patch()

@pytest.mark.vcr(
    filter_headers=["authorization"],
    allowed_hosts=["api.wandb.ai", "localhost"],
)
def test_guardrails_generate(
    client: weave.trace.weave_client.WeaveClient,
    patch_guardrails: None,
) -> None:
    from llmrails import LLMRails
    
    rails = LLMRails(api_key="test-key")
    response = rails.generate(
        prompt="Tell me a joke",
        model="claude-3-sonnet",
        max_tokens=100
    )
    
    # Verify the call was tracked
    calls = list(client.get_calls())
    assert len(calls) == 1
    assert calls[0].name == "llmrails.LLMRails.generate"

@pytest.mark.vcr(
    filter_headers=["authorization"],
    allowed_hosts=["api.wandb.ai", "localhost"],
)
def test_guardrails_evaluate(
    client: weave.trace.weave_client.WeaveClient,
    patch_guardrails: None,
) -> None:
    from llmrails import LLMRails
    
    rails = LLMRails(api_key="test-key")
    response = rails.evaluate(
        text="This is a test response",
        criteria="Check for profanity"
    )
    
    # Verify the call was tracked
    calls = list(client.get_calls())
    assert len(calls) == 1
    assert calls[0].name == "llmrails.LLMRails.evaluate"