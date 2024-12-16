import pytest
from transformers import AutoTokenizer
from unittest.mock import MagicMock
import wandb

import weave
from weave.scorers import LlamaGuard

_TINY_MODEL_NAME = "HuggingFaceM4/tiny-random-LlamaForCausalLM"
_LLAMAGUARD_MODEL_NAME = "meta-llama/Llama-Guard-3-1B"


@pytest.fixture
def llamaguard_scorer(monkeypatch):
    # Mock model loading functions
    monkeypatch.setattr("weave.scorers.llm_utils.download_model", lambda *args, **kwargs: None)
    monkeypatch.setattr("weave.scorers.llm_utils.MODEL_PATHS", {"llamaguard": "mock_path"})
    monkeypatch.setattr("weave.scorers.llm_utils.LOCAL_MODEL_DIR", "/tmp/mock_models")
    monkeypatch.setattr("weave.scorers.llm_utils.get_model_path", lambda *args: "mock_path")

    scorer = LlamaGuard(
        model_name=_TINY_MODEL_NAME,
        device="cpu",
        name="test-llamaguard",
        description="Test LlamaGuard scorer",
        column_map={"output": "text"}
    )

    # Mock model and tokenizer
    monkeypatch.setattr(scorer, "model_post_init", lambda *args: None)
    monkeypatch.setattr(scorer, "_model", MagicMock())
    monkeypatch.setattr(scorer, "_tokenizer", MagicMock())
    monkeypatch.setattr(scorer, "__private_attributes__", {
        "_model": None,
        "_tokenizer": None,
        "device": "cpu",
        "model_name": _TINY_MODEL_NAME,
        "name": "test-llamaguard",
        "description": "Test LlamaGuard scorer",
        "column_map": {"output": "text"},
        "model_post_init": None
    })
    monkeypatch.setattr(scorer, "__pydantic_private__", {})
    monkeypatch.setattr(scorer, "__pydantic_fields__", {
        "_model": None,
        "_tokenizer": None,
        "device": "cpu",
        "model_name": _TINY_MODEL_NAME,
        "name": "test-llamaguard",
        "description": "Test LlamaGuard scorer",
        "column_map": {"output": "text"},
        "model_post_init": None
    })
    monkeypatch.setattr(scorer, "__pydantic_extra__", {})

    # Mock the _generate method to return predictable outputs
    def mock_generate(*args, **kwargs):
        if "unsafe" in str(args) or "bad" in str(args):
            return "unsafe\nS10: Hate<|eot_id|>", 0.85
        return "safe\nNo issues found<|eot_id|>", 0.1

    monkeypatch.setattr(scorer, "_generate", mock_generate)
    return scorer


def test_llamaguard_postprocess(llamaguard_scorer):
    # Test safe content
    safe_output = ("safe", 0.1)
    result = llamaguard_scorer.postprocess(*safe_output)
    assert result["safe"]
    assert result["category"] is None
    assert result["unsafe_score"] == 0.1

    # Test unsafe content with category
    unsafe_output = ("unsafe\nS5<|eot_id|>", 0.9)
    result = llamaguard_scorer.postprocess(*unsafe_output)
    assert not result["safe"]
    assert result["category"] == "S5: Defamation"
    assert result["unsafe_score"] == 0.9


@pytest.mark.asyncio
async def test_llamaguard_score(llamaguard_scorer):
    output = "Test content for scoring"
    result = await llamaguard_scorer.score(output=output)
    assert isinstance(result, dict)
    assert "safe" in result
    assert "category" in result
    assert "unsafe_score" in result
    assert result["safe"] is False
    assert result["category"] == "S10: Hate"
    assert result["unsafe_score"] == 0.85


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
