from typing import TYPE_CHECKING, Any, Optional

from presidio_analyzer import EntityRecognizer
from pydantic import BaseModel

import weave
from weave import Scorer

if TYPE_CHECKING:
    from presidio_analyzer import AnalyzerEngine, RecognizerResult
    from presidio_anonymizer import AnonymizerEngine


class PresidioEntityRecognitionResponse(BaseModel):
    flagged: bool
    detected_entities: dict[str, list[str]]
    reason: str
    anonymized_text: Optional[str] = None


class PresidioEntityRecognitionGuardrail(Scorer):
    """
    The `PresidioEntityRecognitionGuardrail` class is a guardrail for entity recognition and anonymization
    by leveraging Presidio's AnalyzerEngine and AnonymizerEngine to perform these tasks.

    Attributes:
        selected_entities (Optional[list[str]]): A list of entity types to detect in the text.
        should_anonymize (bool): A flag indicating whether detected entities should be anonymized.
        language (str): The language of the text to be analyzed.
        deny_lists (Optional[dict[str, list[str]]]): A dictionary of entity types and their
            corresponding deny lists.
        regex_patterns (Optional[dict[str, list[dict[str, str]]]]): A dictionary of entity
            types and their corresponding regex patterns.
        custom_recognizers (Optional[list[dict[str, Any]]]): A list of dictionaries representing
            custom recognizers to add to the analyzer.
        show_available_entities (bool): A flag indicating whether to print available entities.
    """

    @staticmethod
    def get_available_entities() -> list[str]:
        """Get available entities from Presidio"""
        from presidio_analyzer import AnalyzerEngine, RecognizerRegistry

        registry = RecognizerRegistry()
        analyzer = AnalyzerEngine(registry=registry)
        return [
            recognizer.supported_entities[0]
            for recognizer in analyzer.registry.recognizers
        ]

    selected_entities: list[str] = []
    language: str = "en"
    deny_lists: Optional[dict[str, list[str]]] = None
    regex_patterns: Optional[dict[str, list[dict[str, str]]]] = None
    custom_recognizers: Optional[list[dict[str, Any]]] = None
    show_available_entities: bool = False
    _analyzer: Optional["AnalyzerEngine"] = None
    _anonymizer: Optional["AnonymizerEngine"] = None

    def __init__(self, **data: Any):
        super().__init__(**data)

    def model_post_init(self, __context: Any) -> None:
        from presidio_analyzer import AnalyzerEngine, Pattern, PatternRecognizer
        from presidio_anonymizer import AnonymizerEngine

        # If show_available_entities is True, print available entities
        if self.show_available_entities:
            available_entities = self.get_available_entities()
            print("\nAvailable entities:")
            print("=" * 25)
            for entity in available_entities:
                print(f"- {entity}")
            print("=" * 25 + "\n")

        # Initialize default values to all available entities
        if self.selected_entities is None:
            self.selected_entities = self.get_available_entities()

        # Get available entities dynamically
        available_entities = self.get_available_entities()

        # Filter out invalid entities and warn user
        invalid_entities = [
            e for e in self.selected_entities if e not in available_entities
        ]
        valid_entities = [e for e in self.selected_entities if e in available_entities]

        if invalid_entities:
            print(
                f"\nWarning: The following entities are not available and will be ignored: {invalid_entities}"
            )
            print(f"Continuing with valid entities: {valid_entities}")
            self.selected_entities = valid_entities

        # Initialize analyzer with default recognizers
        self._analyzer = AnalyzerEngine()

        # Add custom recognizers if provided
        if self.custom_recognizers:
            for recognizer_data in self.custom_recognizers:
                recognizer = EntityRecognizer.from_dict(recognizer_data)
                self._analyzer.registry.add_recognizer(recognizer)

        # Add deny list recognizers if provided
        if self.deny_lists:
            for entity_type, tokens in self.deny_lists.items():
                deny_list_recognizer = PatternRecognizer(
                    supported_entity=entity_type, deny_list=tokens
                )
                self._analyzer.registry.add_recognizer(deny_list_recognizer)

        # Add regex pattern recognizers if provided
        if self.regex_patterns:
            for entity_type, patterns in self.regex_patterns.items():
                presidio_patterns = [
                    Pattern(
                        name=pattern.get("name", f"pattern_{i}"),
                        regex=pattern["regex"],
                        score=pattern.get("score", 0.5),
                    )
                    for i, pattern in enumerate(patterns)
                ]
                regex_recognizer = PatternRecognizer(
                    supported_entity=entity_type, patterns=presidio_patterns
                )
                self._analyzer.registry.add_recognizer(regex_recognizer)

        self._anonymizer = AnonymizerEngine()

    def group_analyzer_results_by_entity_type(
        self, output: str, analyzer_results: list[Any]
    ) -> dict[str, list[str]]:
        """Group results by entity type"""
        detected_entities: dict[str, list[str]] = {}
        for result in analyzer_results:
            entity_type = result.entity_type
            text_slice = output[result.start : result.end]
            if entity_type not in detected_entities:
                detected_entities[entity_type] = []
            detected_entities[entity_type].append(text_slice)
        return detected_entities

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
        for entity in self.selected_entities:
            explanation_parts.append(f"- {entity}")

        return "\n".join(explanation_parts)

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
    def score(self, output: str) -> dict[str, Any]:
        if self._analyzer is None:
            raise ValueError("Analyzer is not initialized")

        analyzer_results = self._analyzer.analyze(
            text=str(output), entities=self.selected_entities, language=self.language
        )
        detected_entities = self.group_analyzer_results_by_entity_type(
            output, analyzer_results
        )
        reason = self.create_reason(detected_entities)
        anonymized_text = self.anonymize_text(
            output, analyzer_results, detected_entities
        )
        return PresidioEntityRecognitionResponse(
            flagged=bool(detected_entities),
            detected_entities=detected_entities,
            reason=reason,
            anonymized_text=anonymized_text,
        ).model_dump()
