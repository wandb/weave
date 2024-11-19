import pytest
import weave
from weave.scorers.secrets_scorer import SecretsScorer, REDACTION


@pytest.fixture
def secrets_scorer():
    return SecretsScorer()


def test_secrets_scorer_initialization(secrets_scorer):
    assert isinstance(secrets_scorer, SecretsScorer)
    assert secrets_scorer.redact_mode == REDACTION.REDACT_ALL


def test_secrets_scorer_get_unique_secrets(secrets_scorer):
    input_text = 'I need to pass a key\naws_secret_access_key="wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"'
    unique_secrets, lines = secrets_scorer.get_unique_secrets(input_text)
    assert isinstance(unique_secrets, dict)
    assert "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY" in unique_secrets
    assert unique_secrets["wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"] == [2]
    assert lines == [
        "I need to pass a key",
        'aws_secret_access_key="wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"',
    ]


def test_secrets_scorer_get_modified_value(secrets_scorer):
    unique_secrets = {"wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY": [2]}
    lines = [
        "I need to pass a key",
        'aws_secret_access_key="wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"',
    ]
    modified_value = secrets_scorer.get_modified_value(unique_secrets, lines)
    assert modified_value == 'I need to pass a key\naws_secret_access_key="******"'


@pytest.mark.asyncio
async def test_secrets_scorer_score(secrets_scorer):
    input_text = 'I need to pass a key\naws_secret_access_key="wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"'
    output_text = 'I need to pass a key\naws_secret_access_key="******"'
    result = await secrets_scorer.score(input=input_text, output=output_text)
    assert isinstance(result, dict)
    assert "input_secrets" in result
    assert "output_secrets" in result
    assert result["input_secrets"]["detected_secrets"] == ["detected"]
    assert result["output_secrets"]["detected_secrets"] == []
    assert result["total_secrets"] == 1
    assert result["input_has_secrets"] is True
    assert result["output_has_secrets"] is False


@pytest.mark.asyncio
async def test_evaluate_secrets_scorer(secrets_scorer):
    dataset = [
        {
            "input": 'I need to pass a key\naws_secret_access_key="wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"',
        },
        {
            "input": "My github token is: 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",
        },
        {
            "input": "My JWT token is: eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0IjoxNTE2MjM5MDIyfQ.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c",
        },
    ]
    evaluation = weave.Evaluation(dataset=dataset, scorers=[secrets_scorer])

    @weave.op
    def model(input: str):
        return (
            input.replace("wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY", "******")
            .replace("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", "******")
            .replace(
                "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0IjoxNTE2MjM5MDIyfQ.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c",
                "******",
            )
        )

    result = await evaluation.evaluate(model)
    assert isinstance(result, dict)
    assert "SecretsScorer" in result
    assert result["SecretsScorer"]["total_secrets"]["mean"] == 1.0
    assert result["SecretsScorer"]["input_has_secrets"]["true_count"] == 3
    assert result["SecretsScorer"]["input_has_secrets"]["true_fraction"] == 1.0
