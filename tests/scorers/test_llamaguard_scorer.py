import pytest
from openai import OpenAI
import torch
from transformers import AutoTokenizer

import weave
from weave.scorers import LlamaGuard

_TINY_MODEL_NAME = "HuggingFaceM4/tiny-random-LlamaForCausalLM"
_LLAMAGUARD_MODEL_NAME = "meta-llama/Llama-Guard-3-1B"

@pytest.fixture
def llamaguard_scorer(monkeypatch):
    scorer = LlamaGuard(
        model_name=_TINY_MODEL_NAME,
        device="cpu",
    )
    scorer._tokenizer = AutoTokenizer.from_pretrained(_LLAMAGUARD_MODEL_NAME) 
    # Mock the _generate method to return predictable outputs
    def mock_generate(*args, **kwargs):
        return "unsafe\nS10: Hate<|eot_id|>"
    
    monkeypatch.setattr(scorer, "_generate", mock_generate)
    return scorer

def test_llamaguard_postprocess(llamaguard_scorer):
    # Test safe content
    safe_output = "safe"
    result = llamaguard_scorer.postprocess(safe_output)
    assert result["safe"]
    assert result["category"] is None

    # Test unsafe content with category
    unsafe_output = "unsafe\nS5<|eot_id|>"
    result = llamaguard_scorer.postprocess(unsafe_output)
    assert not result["safe"]
    assert result["category"] == "S5: Defamation"


@pytest.mark.asyncio
async def test_llamaguard_score(llamaguard_scorer):
    output = "Test content for scoring"
    result = await llamaguard_scorer.score(output)
    assert isinstance(result, dict)
    assert "safe" in result
    assert "category" in result
    assert result["safe"] is False
    assert result["category"] == "S10: Hate"


@pytest.mark.asyncio
async def test_llamaguard_evaluation(llamaguard_scorer):
    dataset = [
        {"input": "This is a unsafe text."},
        {"input": "This is also bad text"},
    ]

    @weave.op
    def model(input: str):
        return input

    evaluation = weave.Evaluation(
        dataset=dataset,
        scorers=[llamaguard_scorer],
    )
    result = await evaluation.evaluate(model)
    
    assert "LlamaGuard" in result
    assert "safe" in result["LlamaGuard"]
