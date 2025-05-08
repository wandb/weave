import logging
from typing import TYPE_CHECKING, Any, Optional

from pydantic import Field, PrivateAttr

import weave
from weave.flow.scorer import WeaveScorerResult

if TYPE_CHECKING:
    from presidio_analyzer import (
        AnalyzerEngine,
        RecognizerResult,
    )
    from presidio_anonymizer import AnonymizerEngine


logger = logging.getLogger(__name__)


class PresidioScorer(weave.Scorer):
    """
    The `PresidioScorer` class is a guardrail for entity recognition and anonymization
    by leveraging Presidio's AnalyzerEngine and AnonymizerEngine to perform these tasks.

    Attributes:
        selected_entities (list[str]): A list of entity types to detect in the text.
        language (str): The language of the text to be analyzed.
        custom_recognizers (list[EntityRecognizer]): A list of custom recognizers to add to the
            analyzer that are of type `presidio.EntityRecognizer`.

    Offline mode for presidio: https://github.com/microsoft/presidio/discussions/1435
    """

    language: str = Field(
        default="en", description="The language of the text to be analyzed."
    )
    custom_recognizers: list[Any] = Field(
        default_factory=list,
        description="A list of custom recognizers to add to the analyzer. Check Presidio's documentation for more information; https://microsoft.github.io/presidio/samples/python/customizing_presidio_analyzer/",
    )

    selected_entities: Optional[list[str]] = Field(
        default=None,
        description="A list of entity types to detect in the text.",
        examples=[["EMAIL_ADDRESS"]],
    )

    # Private attributes
    _analyzer: Optional["AnalyzerEngine"] = PrivateAttr(default=None)
    _anonymizer: Optional["AnonymizerEngine"] = PrivateAttr(default=None)

    def model_post_init(self, __context: Any) -> None:
        from presidio_analyzer import AnalyzerEngine, RecognizerRegistry
        from presidio_anonymizer import AnonymizerEngine

        registry = RecognizerRegistry()
        self._analyzer = AnalyzerEngine(registry=registry)
        self._anonymizer = AnonymizerEngine()

        # Add custom recognizers if provided
        if self.custom_recognizers:
            for recognizer in self.custom_recognizers:
                self._analyzer.registry.add_recognizer(recognizer)

        # Get available entities dynamically
        available_entities = [
            recognizer.supported_entities[0]
            for recognizer in self._analyzer.registry.recognizers
        ]

        if self.selected_entities is not None:
            # Filter out invalid entities and warn user
            invalid_entities = list(
                set(self.selected_entities) - set(available_entities)
            )
            valid_entities = list(
                set(self.selected_entities).intersection(available_entities)
            )

            if invalid_entities:
                logger.warning(
                    f"\nThe following entities are not available and will be ignored: {invalid_entities}\nContinuing with valid entities: {valid_entities}"
                )
                self.selected_entities = valid_entities
        else:
            self.selected_entities = available_entities

    @weave.op
    def group_analyzer_results_by_entity_type(
        self, output: str, analyzer_results: list["RecognizerResult"]
    ) -> dict[str, list[str]]:
        """Group results by entity type"""
        detected_entities: dict[str, list[str]] = {}
        for result in analyzer_results:
            entity_type = result.entity_type
            text_chunk = output[result.start : result.end]
            if entity_type not in detected_entities:
                detected_entities[entity_type] = []
            detected_entities[entity_type].append(text_chunk)
        return detected_entities

    @weave.op
    def create_reason(self, detected_entities: dict[str, list[str]]) -> str:
        """Create explanation for why the text was flagged"""
        explanation_parts = []
        if detected_entities:
            explanation_parts.append("Found the following entities in the text:")
            for entity_type, instances in detected_entities.items():
                explanation_parts.append(
                    f"- {entity_type}: {len(instances)} instance(s)"
                )
        else:
            explanation_parts.append("No entities detected in the text.")

        # Add information about what was checked
        explanation_parts.append("\nChecked for these entity types:")
        if self.selected_entities is not None:
            for entity in self.selected_entities:
                explanation_parts.append(f"- {entity}")
        return "\n".join(explanation_parts)

    @weave.op
    def anonymize_text(
        self,
        output: str,
        analyzer_results: list["RecognizerResult"],
        detected_entities: dict[str, list[str]],
    ) -> Optional[str]:
        anonymized_text = None
        if detected_entities and self._anonymizer is not None:
            anonymized_result = self._anonymizer.anonymize(
                text=output, analyzer_results=analyzer_results
            )
            anonymized_text = anonymized_result.text
        return anonymized_text

    @weave.op
    def score(
        self, *, output: str, entities: Optional[list[str]] = None, **kwargs: Any
    ) -> WeaveScorerResult:
        if self._analyzer is None:
            raise ValueError("Analyzer is not initialized")
        if entities is None:
            entities = self.selected_entities
        analyzer_results = self._analyzer.analyze(
            text=str(output), entities=entities, language=self.language
        )
        detected_entities = self.group_analyzer_results_by_entity_type(
            output, analyzer_results
        )
        reason = self.create_reason(detected_entities)
        anonymized_text = self.anonymize_text(
            output, analyzer_results, detected_entities
        )
        return WeaveScorerResult(
            passed=not bool(detected_entities),
            metadata={
                "detected_entities": detected_entities,
                "reason": reason,
                "anonymized_text": anonymized_text,
            },
        )
