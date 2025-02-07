import re
from typing import Any, Optional, Union

from pydantic import BaseModel

import weave
from weave import Scorer
from weave.flow.model import Model
from weave.scorers.utils import stringify

DEFAULT_PATTERNS = {
    "EMAIL": r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b",
    "TELEPHONENUM": r"\b(\+\d{1,3}[-.]?)?\(?\d{3}\)?[-.]?\d{3}[-.]?\d{4}\b",
    "SOCIALNUM": r"\b\d{3}[-]?\d{2}[-]?\d{4}\b",
    "CREDITCARDNUMBER": r"\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b",
    "DATEOFBIRTH": r"\b(0[1-9]|1[0-2])[-/](0[1-9]|[12]\d|3[01])[-/](19|20)\d{2}\b",
    "DRIVERLICENSENUM": r"[A-Z]\d{7}",  # Example pattern, adjust for your needs
    "ACCOUNTNUM": r"\b\d{10,12}\b",  # Example pattern for bank accounts
    "ZIPCODE": r"\b\d{5}(?:-\d{4})?\b",
    "GIVENNAME": r"\b[A-Z][a-z]+\b",  # Basic pattern for first names
    "SURNAME": r"\b[A-Z][a-z]+\b",  # Basic pattern for last names
    "CITY": r"\b[A-Z][a-z]+(?:[\s-][A-Z][a-z]+)*\b",
    "STREET": r"\b\d+\s+[A-Z][a-z]+\s+(?:Street|St|Avenue|Ave|Road|Rd|Boulevard|Blvd|Lane|Ln|Drive|Dr)\b",
    "IDCARDNUM": r"[A-Z]\d{7,8}",  # Generic pattern for ID cards
    "USERNAME": r"@[A-Za-z]\w{3,}",  # Basic username pattern
    "PASSWORD": r"[A-Za-z0-9@#$%^&+=]{8,}",  # Basic password pattern
    "TAXNUM": r"\b\d{2}[-]\d{7}\b",  # Example tax number pattern
    "BUILDINGNUM": r"\b\d+[A-Za-z]?\b",  # Basic building number pattern
}


class RegexResult(BaseModel):
    passed: bool
    matched_patterns: dict[str, list[str]]
    failed_patterns: list[str]


class RegexEntityRecognitionResponse(BaseModel):
    flagged: bool
    detected_entities: dict[str, list[str]]
    reason: str
    anonymized_text: Optional[str] = None


class RegexModel(Model):
    """
    Initialize RegexModel with a dictionary of patterns.

    Attributes:
        patterns (Optional[Union[dict[str, str], dict[str, list[str]]]]): Dictionary where key
            is pattern name and value is regex pattern.
    """

    patterns: Optional[Union[dict[str, str], dict[str, list[str]]]] = None

    def __init__(
        self, patterns: Optional[Union[dict[str, str], dict[str, list[str]]]] = None
    ) -> None:
        super().__init__(patterns=patterns)
        normalized_patterns = {}
        if patterns:
            for k, v in patterns.items():
                normalized_patterns[k] = v if isinstance(v, list) else [v]
        self._compiled_patterns = {
            name: [re.compile(p) for p in pattern]
            for name, pattern in normalized_patterns.items()
        }

    def check(self, text: str) -> RegexResult:
        """
        Check text against all patterns and return detailed results.

        Args:
            text (str): Input text to check against patterns

        Returns:
            RegexResult containing pass/fail status and details about matches
        """
        matched_patterns = {}
        failed_patterns = []

        for pattern_name, pats in self._compiled_patterns.items():
            matches = []
            for pattern in pats:
                for match in pattern.finditer(text):
                    if match.groups():
                        # If there are capture groups, join them with a separator
                        matches.append(
                            "-".join(str(g) for g in match.groups() if g is not None)
                        )
                    else:
                        # If no capture groups, use the full match
                        matches.append(match.group(0))

            if matches:
                matched_patterns[pattern_name] = matches
            else:
                failed_patterns.append(pattern_name)

        return RegexResult(
            matched_patterns=matched_patterns,
            failed_patterns=failed_patterns,
            passed=len(matched_patterns) == 0,
        )

    @weave.op
    def predict(self, text: str) -> RegexResult:
        """Alias for check() to maintain consistency with other models."""
        return self.check(text)


class RegexEntityRecognitionGuardrail(Scorer):
    """
    `RegexEntityRecognitionGuardrail` is a guardrail that uses a regex model to detect
    entities in a text and optionally anonymize them.

    Args:
        should_anonymize (bool): Whether to anonymize the text.
        custom_terms (Optional[list[str]]): The custom terms to use for entity detection.
        aggregate_redaction (bool): Whether to aggregate redactions.

    Attributes:
        regex_model (RegexModel): The regex model to use for entity detection.
        patterns (dict[str, str]): The patterns to use for entity detection.
        should_anonymize (bool): Whether to anonymize the text.
        custom_terms (Optional[list[str]]): The custom terms to use for entity detection.
        aggregate_redaction (bool): Whether to aggregate redactions.
    """

    regex_model: Optional[RegexModel] = None
    patterns: Optional[dict[str, str]] = None
    should_anonymize: bool = False
    custom_terms: Optional[list[str]] = None
    aggregate_redaction: bool = True

    def model_post_init(self, __context: Any) -> None:
        self.patterns = DEFAULT_PATTERNS if self.patterns is None else self.patterns
        self.regex_model = (
            RegexModel(patterns=self.patterns)
            if self.regex_model is None
            else self.regex_model
        )

    def text_to_pattern(self, text: str) -> str:
        """Convert input text into a regex pattern that matches the exact text."""
        # Escape special regex characters in the text
        escaped_text = re.escape(text)
        # Create a pattern that matches the exact text, case-insensitive
        return rf"\b{escaped_text}\b"

    def check_regex_model(self, output: str) -> RegexResult:
        if self.custom_terms:
            # Create a temporary RegexModel with only the custom patterns
            temp_patterns = {
                term: self.text_to_pattern(term) for term in self.custom_terms
            }
            temp_model = RegexModel(patterns=temp_patterns)
            result = temp_model.check(output)
        else:
            # Use the original regex_model if no custom terms provided
            result = self.regex_model.check(output)
        return result

    def get_reasonings(self, result: RegexResult) -> list[str]:
        explanation_parts = []
        if result.matched_patterns:
            explanation_parts.append("Found the following entities in the text:")
            for entity_type, matches in result.matched_patterns.items():
                explanation_parts.append(f"- {entity_type}: {len(matches)} instance(s)")
        else:
            explanation_parts.append("No entities detected in the text.")

        if result.failed_patterns:
            explanation_parts.append("\nChecked but did not find these entity types:")
            for pattern in result.failed_patterns:
                explanation_parts.append(f"- {pattern}")
        return explanation_parts

    def get_anonymized_text(self, output: str, result: RegexResult) -> Union[str, None]:
        anonymized_text = None
        if getattr(self, "should_anonymize", False) and result.matched_patterns:
            anonymized_text = output
            for entity_type, matches in result.matched_patterns.items():
                for match in matches:
                    replacement = (
                        "[redacted]"
                        if self.aggregate_redaction
                        else f"[{entity_type.upper()}]"
                    )
                    anonymized_text = anonymized_text.replace(match, replacement)
        return anonymized_text

    @weave.op
    def score(self, output: str) -> RegexEntityRecognitionResponse:
        output = stringify(output)
        result: RegexResult = self.check_regex_model(output)
        reasonings = self.get_reasonings(result)
        anonymized_text = self.get_anonymized_text(output, result)
        return RegexEntityRecognitionResponse(
            flagged=not result.passed,
            detected_entities=result.matched_patterns,
            reason="\n".join(reasonings),
            anonymized_text=anonymized_text,
        ).model_dump()
