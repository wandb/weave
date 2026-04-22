import pytest
from pydantic import ValidationError

from weave.scorers.remote_scorer import RemoteScorer


def test_remote_scorer_fields() -> None:
    rs = RemoteScorer(
        name="policy_remote",
        endpoint_url="https://scoring.example.com/v1/score",
        config={"threshold": 0.9},
    )
    assert rs.endpoint_url == "https://scoring.example.com/v1/score"
    assert rs.config == {"threshold": 0.9}


def test_remote_scorer_endpoint_url_allows_http_for_local_dev() -> None:
    for url in (
        "http://127.0.0.1:8000/v1/score",
        "http://localhost:3000/score",
    ):
        rs = RemoteScorer(endpoint_url=url)
        assert rs.endpoint_url == url


def test_remote_scorer_endpoint_url_strips_whitespace() -> None:
    rs = RemoteScorer(
        endpoint_url="  https://scoring.example.com/v1  ",
    )
    assert rs.endpoint_url == "https://scoring.example.com/v1"


@pytest.mark.parametrize(
    ("bad_url", "match_substr"),
    [
        ("ftp://example.com/score", "http or https"),
        ("https://", "host"),
        ("not-a-url", "http or https"),
    ],
)
def test_remote_scorer_endpoint_url_rejects_malformed(
    bad_url: str, match_substr: str
) -> None:
    with pytest.raises(ValidationError, match=match_substr):
        RemoteScorer(endpoint_url=bad_url)


def test_remote_scorer_score_raises() -> None:
    rs = RemoteScorer(endpoint_url="https://scoring.example.com/v1/score")
    with pytest.raises(NotImplementedError, match="Weave scoring worker"):
        rs.score(output="x")
