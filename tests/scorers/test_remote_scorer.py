from unittest.mock import patch

import pytest
from pydantic import ValidationError

from weave.scorers.remote_scorer import (
    RemoteScorer,
    _validate_remote_scorer_endpoint_url,
)


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


def test_remote_scorer_endpoint_url_strips_leading_trailing_newlines_and_tabs() -> None:
    rs = RemoteScorer(
        endpoint_url="\thttps://scoring.example.com/v1\n",
    )
    assert rs.endpoint_url == "https://scoring.example.com/v1"


@pytest.mark.parametrize(
    "url",
    [
        "https://scoring.example.com/v1/score",
        "http://127.0.0.1:8000/score",
        "https://scoring.example.com:8443/p",
    ],
)
def test_validate_remote_scorer_endpoint_url_accepts_http_s_with_host(
    url: str,
) -> None:
    assert _validate_remote_scorer_endpoint_url(url) == url


@pytest.mark.parametrize(
    ("url", "message_substr"),
    [
        ("", "http or https"),
        ("https://", "include a host"),
        ("http://", "include a host"),
        ("http:///no-netloc", "include a host"),
        ("ftp://example.com/score", "http or https"),
        ("file:///tmp/score", "http or https"),
        ("not-a-url", "http or https"),
    ],
)
def test_validate_remote_scorer_endpoint_url_rejects(
    url: str,
    message_substr: str,
) -> None:
    with pytest.raises(ValueError, match=message_substr):
        _validate_remote_scorer_endpoint_url(url)


def test_validate_remote_scorer_endpoint_url_urlparse_exception_is_wrapped() -> None:
    with patch(
        "weave.scorers.remote_scorer.urlparse", side_effect=OSError("parse failed")
    ):
        with pytest.raises(
            ValueError, match="endpoint_url must be a valid URL string"
        ) as exc_info:
            _validate_remote_scorer_endpoint_url("https://example.com/x")
    assert exc_info.value.__cause__ is not None


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


def test_remote_scorer_score_raises_not_implemented() -> None:
    rs = RemoteScorer(endpoint_url="https://scoring.example.com/v1/score")
    with pytest.raises(NotImplementedError) as exc_info:
        rs.score(output="x")
    assert str(exc_info.value) == (
        "RemoteScorer is run by the Weave scoring worker against your HTTPS "
        "endpoint; score() is not part of that path."
    )
