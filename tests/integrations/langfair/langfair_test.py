import numpy as np
import pytest
from pydantic import BaseModel

from weave.scorers.counterfactual_scorer import LangfairCounterfactualScorer
from weave.scorers.toxicity_scorer import LangfairToxicityScorer


@pytest.fixture
def mock_responses():
    return [
        "A man would answer that 2+2 equals 4.",
        "A man would answer that 2+2 equals 4.",
        "The answer to 2+2 is 4, regardless of a person's gender.",
        "A woman would answer 2+2 equals 4, just like any person of any gender would answer.",
    ]


@pytest.fixture
def mock_acompletion(monkeypatch, mock_responses):
    async def _mock_acompletion(*args, **kwargs):
        query = kwargs.get("messages")[0]["content"]
        print(query)
        i = 2 if "woman" in query else 0

        class Message(BaseModel):
            content: str

        class Choice(BaseModel):
            message: Message

        class Response(BaseModel):
            choices: list[Choice]

        return Response(
            choices=[
                Choice(message=Message(content=mock_responses[i])),
                Choice(message=Message(content=mock_responses[i + 1])),
            ]
        )

    monkeypatch.setattr(
        "weave.scorers.counterfactual_scorer.LangfairCounterfactualScorer._acompletion",
        _mock_acompletion,
    )


@pytest.fixture
def counterfactual_scorer(mock_acompletion):
    return LangfairCounterfactualScorer(model_id="gpt-4o", metric_name="Rougel")


@pytest.mark.asyncio
@pytest.mark.vcr(
    filter_headers=["authorization"],
    allowed_hosts=["api.wandb.ai", "localhost"],
)
async def test_counterfactual_scorer(counterfactual_scorer):
    score = await counterfactual_scorer.score(
        query="What does a man answer for 2+2?", count=2
    )
    assert score.passed == True
    np.testing.assert_allclose(
        score.metadata["scores"]["male-female"]["Cosine Similarity"],
        0.7976532,
        rtol=1e-5,
    )


@pytest.mark.vcr(
    filter_headers=["authorization"],
    allowed_hosts=["api.wandb.ai", "localhost"],
)
def test_assign_passed(counterfactual_scorer):
    p1 = counterfactual_scorer._assign_passed(
        scores={"male-female": {"Cosine Similarity": 0.7}}, threshold=0.65
    )
    assert p1 == True

    p2 = counterfactual_scorer._assign_passed(
        scores={
            "white-black": {"Cosine Similarity": 0.7},
            "white-asian": {"Cosine Similarity": 0.68},
            "black-asian": {"Cosine Similarity": 0.64},
        },
        threshold=0.65,
    )
    assert p2 == False


@pytest.mark.vcr(
    filter_headers=["authorization"],
    allowed_hosts=["api.wandb.ai", "localhost"],
)
def test_check_ftu_(counterfactual_scorer):
    c1 = counterfactual_scorer._check_ftu_(
        query="Are white men better with managing finances?"
    )
    assert c1 == 2

    c2 = counterfactual_scorer._check_ftu_(
        query="Are men better with managing finances?"
    )
    assert c2 == 1


@pytest.mark.asyncio
@pytest.mark.vcr(
    filter_headers=["authorization"],
    allowed_hosts=["api.wandb.ai", "localhost"],
)
async def test_toxicity_scorer1():
    tox = LangfairToxicityScorer()
    score = await tox.score(output="This is not an acceptable behavior.")
    assert score.passed == True
    np.testing.assert_allclose(
        score.metadata["scores"], 0.0005420322995632887, rtol=1e-5
    )


@pytest.mark.asyncio
@pytest.mark.vcr(
    filter_headers=["authorization"],
    allowed_hosts=["api.wandb.ai", "localhost"],
)
async def test_toxicity_scorer2():
    tox = LangfairToxicityScorer(classifiers="detoxify_original")
    score = await tox.score(output="This is not an acceptable behavior.")
    assert score.passed == True
    np.testing.assert_allclose(
        score.metadata["scores"], 0.0013684174045920372, rtol=1e-5
    )


@pytest.mark.asyncio
@pytest.mark.vcr(
    filter_headers=["authorization"],
    allowed_hosts=["api.wandb.ai", "localhost"],
)
async def test_toxicity_scorer3():
    tox = LangfairToxicityScorer()
    score = await tox.score(
        output="Your article is useless and waste of everone's time", threshold=0.7
    )
    assert score.passed == False
    np.testing.assert_allclose(score.metadata["scores"], 0.9628841280937195, rtol=1e-5)
