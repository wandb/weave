import numpy as np
import pytest

from weave.scorers.toxicity_scorer import ToxicityScorer


@pytest.mark.asyncio
async def test_toxicity_scorer1():
    tox = ToxicityScorer()
    score = await tox.score(output="This is not an acceptable behavior.")
    assert score.passed == True
    np.testing.assert_allclose(
        score.metadata["scores"], 0.0005420322995632887, rtol=1e-5
    )


@pytest.mark.asyncio
async def test_toxicity_scorer2():
    tox = ToxicityScorer(classifiers="detoxify_original")
    score = await tox.score(output="This is not an acceptable behavior.")
    assert score.passed == True
    np.testing.assert_allclose(
        score.metadata["scores"], 0.0013684174045920372, rtol=1e-5
    )


@pytest.mark.asyncio
async def test_toxicity_scorer3():
    tox = ToxicityScorer()
    score = await tox.score(
        output="Your article is useless and waste of everone's time", threshold=0.7
    )
    assert score.passed == False
    np.testing.assert_allclose(score.metadata["scores"], 0.9628841280937195, rtol=1e-5)
