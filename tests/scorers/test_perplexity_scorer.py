import pytest  # type: ignore

pytestmark = pytest.mark.skip(reason="Test file ignored")

from weave.scorers import HuggingFacePerplexityScorer  # , OpenAIPerplexityScorer

# @pytest.fixture
# def openai_perplexity_scorer():
#     return OpenAIPerplexityScorer()


def test_openai_perplexity_scorer_with_logprobs(openai_perplexity_scorer):
    from openai.types.chat.chat_completion import (
        ChatCompletion,
        ChatCompletionMessage,
        ChatCompletionTokenLogprob,
        Choice,
        ChoiceLogprobs,
    )
    from openai.types.completion_usage import (
        CompletionTokensDetails,
        CompletionUsage,
        PromptTokensDetails,
    )

    # Simulate OpenAI ChatCompletion output
    output = ChatCompletion(
        id="chatcmpl-AZwjre30qbCnZUE5WP8UzBhAzLgZx",
        choices=[
            Choice(
                finish_reason="stop",
                index=0,
                logprobs=ChoiceLogprobs(
                    content=[
                        ChatCompletionTokenLogprob(
                            token="It",
                            bytes=[73, 116],
                            logprob=-4.723352e-06,
                            top_logprobs=[],
                        ),
                        ChatCompletionTokenLogprob(
                            token=" seems",
                            bytes=[32, 115, 101, 101, 109, 115],
                            logprob=-0.25715515,
                            top_logprobs=[],
                        ),
                        ChatCompletionTokenLogprob(
                            token=" like",
                            bytes=[32, 108, 105, 107, 101],
                            logprob=-0.25322762,
                            top_logprobs=[],
                        ),
                        ChatCompletionTokenLogprob(
                            token=" your",
                            bytes=[32, 121, 111, 117, 114],
                            logprob=-9.627177e-05,
                            top_logprobs=[],
                        ),
                        ChatCompletionTokenLogprob(
                            token=" question",
                            bytes=[32, 113, 117, 101, 115, 116, 105, 111, 110],
                            logprob=-0.16034457,
                            top_logprobs=[],
                        ),
                        ChatCompletionTokenLogprob(
                            token=" got",
                            bytes=[32, 103, 111, 116],
                            logprob=-0.20870712,
                            top_logprobs=[],
                        ),
                        ChatCompletionTokenLogprob(
                            token=" cut",
                            bytes=[32, 99, 117, 116],
                            logprob=-4.406056e-05,
                            top_logprobs=[],
                        ),
                        ChatCompletionTokenLogprob(
                            token=" off",
                            bytes=[32, 111, 102, 102],
                            logprob=-9.0883464e-07,
                            top_logprobs=[],
                        ),
                        ChatCompletionTokenLogprob(
                            token=".", bytes=[46], logprob=-0.01260725, top_logprobs=[]
                        ),
                        ChatCompletionTokenLogprob(
                            token=" Could",
                            bytes=[32, 67, 111, 117, 108, 100],
                            logprob=-0.009485474,
                            top_logprobs=[],
                        ),
                        ChatCompletionTokenLogprob(
                            token=" you",
                            bytes=[32, 121, 111, 117],
                            logprob=0.0,
                            top_logprobs=[],
                        ),
                        ChatCompletionTokenLogprob(
                            token=" please",
                            bytes=[32, 112, 108, 101, 97, 115, 101],
                            logprob=-0.0019454146,
                            top_logprobs=[],
                        ),
                        ChatCompletionTokenLogprob(
                            token=" provide",
                            bytes=[32, 112, 114, 111, 118, 105, 100, 101],
                            logprob=-0.0022721777,
                            top_logprobs=[],
                        ),
                        ChatCompletionTokenLogprob(
                            token=" more",
                            bytes=[32, 109, 111, 114, 101],
                            logprob=-0.0008198729,
                            top_logprobs=[],
                        ),
                        ChatCompletionTokenLogprob(
                            token=" details",
                            bytes=[32, 100, 101, 116, 97, 105, 108, 115],
                            logprob=-0.022451635,
                            top_logprobs=[],
                        ),
                        ChatCompletionTokenLogprob(
                            token=" or",
                            bytes=[32, 111, 114],
                            logprob=-0.018980175,
                            top_logprobs=[],
                        ),
                        ChatCompletionTokenLogprob(
                            token=" clarify",
                            bytes=[32, 99, 108, 97, 114, 105, 102, 121],
                            logprob=-0.16709846,
                            top_logprobs=[],
                        ),
                        ChatCompletionTokenLogprob(
                            token=" what",
                            bytes=[32, 119, 104, 97, 116],
                            logprob=-0.0022015248,
                            top_logprobs=[],
                        ),
                        ChatCompletionTokenLogprob(
                            token=" you",
                            bytes=[32, 121, 111, 117],
                            logprob=-0.65700674,
                            top_logprobs=[],
                        ),
                        ChatCompletionTokenLogprob(
                            token=" would",
                            bytes=[32, 119, 111, 117, 108, 100],
                            logprob=-0.0134235,
                            top_logprobs=[],
                        ),
                        ChatCompletionTokenLogprob(
                            token=" like",
                            bytes=[32, 108, 105, 107, 101],
                            logprob=0.0,
                            top_logprobs=[],
                        ),
                        ChatCompletionTokenLogprob(
                            token=" to",
                            bytes=[32, 116, 111],
                            logprob=-7.465036e-06,
                            top_logprobs=[],
                        ),
                        ChatCompletionTokenLogprob(
                            token=" know",
                            bytes=[32, 107, 110, 111, 119],
                            logprob=-0.014183719,
                            top_logprobs=[],
                        ),
                        ChatCompletionTokenLogprob(
                            token="?",
                            bytes=[63],
                            logprob=-6.0153056e-05,
                            top_logprobs=[],
                        ),
                    ],
                    refusal=None,
                ),
                message=ChatCompletionMessage(
                    content="It seems like your question got cut off. Could you please provide more details or clarify what you would like to know?",
                    refusal=None,
                    role="assistant",
                    audio=None,
                    function_call=None,
                    tool_calls=None,
                ),
            )
        ],
        created=1733130635,
        model="gpt-4o-mini-2024-07-18",
        object="chat.completion",
        service_tier=None,
        system_fingerprint="fp_0705bf87c0",
        usage=CompletionUsage(
            completion_tokens=24,
            prompt_tokens=11,
            total_tokens=35,
            completion_tokens_details=CompletionTokensDetails(
                accepted_prediction_tokens=0,
                audio_tokens=0,
                reasoning_tokens=0,
                rejected_prediction_tokens=0,
            ),
            prompt_tokens_details=PromptTokensDetails(audio_tokens=0, cached_tokens=0),
        ),
    )

    result = openai_perplexity_scorer.score(output)
    assert "perplexity" in result
    assert result["perplexity"] == 1.0779795472068388


def test_openai_perplexity_scorer_with_list_logprobs(openai_perplexity_scorer):
    logprobs = [-0.5, -0.6, -0.7, -0.3, -0.4, -0.2]
    result = openai_perplexity_scorer.score(logprobs)
    assert "perplexity" in result
    assert result["perplexity"] == 1.568312185490169


def test_openai_perplexity_scorer_invalid_input(openai_perplexity_scorer):
    with pytest.raises(TypeError, match="Invalid input type!"):
        openai_perplexity_scorer.score(output={"invalid": "data"})


@pytest.fixture
def huggingface_perplexity_scorer():
    return HuggingFacePerplexityScorer()


@pytest.fixture
def hf_output():
    import torch

    logits = torch.tensor(
        [[[0.1, 0.2, 0.7], [0.3, 0.4, 0.3], [0.8, 0.1, 0.1]]]
    )  # Shape: (1, 3, 3)
    input_ids = torch.tensor([[2, 0, 1]])  # Shape: (1, 3)
    return {"logits": logits, "input_ids": input_ids}


def test_huggingface_perplexity_scorer(huggingface_perplexity_scorer, hf_output):
    result = huggingface_perplexity_scorer.score(hf_output)
    assert "perplexity" in result
    assert result["perplexity"] > 0


def test_huggingface_perplexity_scorer_invalid_input(huggingface_perplexity_scorer):
    import torch

    with pytest.raises(KeyError, match="'logits'"):
        huggingface_perplexity_scorer.score(
            output={"input_ids": torch.tensor([[2, 0, 1]])}
        )
