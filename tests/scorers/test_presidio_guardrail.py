import pytest
from presidio_analyzer import EntityRecognizer, RecognizerResult
from presidio_analyzer.nlp_engine import NlpArtifacts

from weave.scorers import PresidioScorer


@pytest.fixture
def presidio_entity_recognition_guardrail():
    return PresidioScorer()


def test_presidio_email_detection(presidio_entity_recognition_guardrail):
    """
    Given a text that contains an email address, the scorer should detect the email
    and mark the result as not passing.
    """
    input_text = "My is thomas@gmail.com"
    result = presidio_entity_recognition_guardrail.score(input_text)

    # Since an entity is detected, we expect the overall result to fail.
    assert not result.passed, "Expected result to fail when an email is detected."

    # Check that the detected entities include the expected email.
    detected_emails = result.metadata["detected_entities"].get("EMAIL_ADDRESS", [])
    assert (
        "thomas@gmail.com" in detected_emails
    ), "Expected to detect 'thomas@gmail.com' as an EMAIL_ADDRESS."


# A custom recognizer to detect numbers by checking each token's `like_num` attribute.
class NumbersRecognizer(EntityRecognizer):
    expected_confidence_level = 0.7  # expected confidence level for this recognizer

    def load(self) -> None:
        """No loading is required."""
        pass

    def analyze(
        self, text: str, entities: list[str], nlp_artifacts: NlpArtifacts
    ) -> list[RecognizerResult]:
        "Analyze the text to locate tokens which represent numbers"
        results = []
        for token in nlp_artifacts.tokens:
            if token.like_num:
                result = RecognizerResult(
                    entity_type="NUMBER",
                    start=token.idx,
                    end=token.idx + len(token.text),
                    score=self.expected_confidence_level,
                )
                results.append(result)
        return results


def test_presidio_scoring_with_custom_number_recognizer():
    """
    Given a text with numerical tokens, the custom numbers recognizer should
    detect each number correctly and the overall result should fail.
    """
    # Instantiate the custom numbers recognizer.
    new_numbers_recognizer = NumbersRecognizer(supported_entities=["NUMBER"])

    # Create a PresidioScorer with the custom recognizer.
    scorer = PresidioScorer(custom_recognizers=[new_numbers_recognizer])
    input_text = "Roberto lives in Five 10 Broad st."
    result = scorer.score(input_text)

    # Check that the custom recognizer detected numbers.
    detected_numbers = result.metadata["detected_entities"].get("NUMBER", [])
    assert detected_numbers, "Custom number recognizer did not detect any numbers."

    # We expect the custom recognizer to separately detect 'Five' and '10'.
    assert set(detected_numbers) == {
        "Five",
        "10",
    }, f"Expected detected numbers to be {{'Five', '10'}}, got {detected_numbers}"

    # Since at least one entity is detected, the result should not pass.
    assert not result.passed, "Result should not pass when numbers are detected."
