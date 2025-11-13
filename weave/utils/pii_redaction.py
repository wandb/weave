import dataclasses
from typing import Any, Optional, Union

from presidio_analyzer import AnalyzerEngine
from presidio_anonymizer import AnonymizerEngine

from weave.telemetry import trace_sentry
from weave.trace.settings import redact_pii_fields
from weave.utils.sanitize import REDACTED_VALUE, redact_dataclass_fields, should_redact

DEFAULT_REDACTED_FIELDS = [
    "CREDIT_CARD",
    "CRYPTO",
    "EMAIL_ADDRESS",
    "IBAN_CODE",
    "IP_ADDRESS",
    "LOCATION",
    "PERSON",
    "PHONE_NUMBER",
    "US_SSN",
    "US_BANK_NUMBER",
    "US_DRIVER_LICENSE",
    "US_PASSPORT",
    "UK_NHS",
    "UK_NINO",
    "ES_NIF",
    "IN_AADHAAR",
    "IN_PAN",
    "FI_PERSONAL_IDENTITY_CODE",
]

# Singleton instances for performance
_analyzer_instance: Optional[AnalyzerEngine] = None
_anonymizer_instance: Optional[AnonymizerEngine] = None


def _get_analyzer() -> AnalyzerEngine:
    """Get or create singleton AnalyzerEngine instance."""
    global _analyzer_instance
    if _analyzer_instance is None:
        _analyzer_instance = AnalyzerEngine()
    return _analyzer_instance


def _get_anonymizer() -> AnonymizerEngine:
    """Get or create singleton AnonymizerEngine instance."""
    global _anonymizer_instance
    if _anonymizer_instance is None:
        _anonymizer_instance = AnonymizerEngine()
    return _anonymizer_instance


def redact_pii(
    data: Union[dict[str, Any], str],
) -> Union[dict[str, Any], str]:
    """Redact PII from data using Microsoft Presidio recursively."""
    analyzer = _get_analyzer()
    anonymizer = _get_anonymizer()
    fields = redact_pii_fields()
    entities = DEFAULT_REDACTED_FIELDS if len(fields) == 0 else fields

    def redact_recursive(value: Any) -> Any:
        if isinstance(value, str):
            results = analyzer.analyze(text=value, language="en", entities=entities)
            if not results:
                return value

            redacted = anonymizer.anonymize(text=value, analyzer_results=results)
            return redacted.text
        elif isinstance(value, dict):
            result = {}
            for k, v in value.items():
                # Check if this key should be redacted based on custom redact keys
                if isinstance(k, str) and should_redact(k):
                    result[k] = REDACTED_VALUE
                else:
                    result[k] = redact_recursive(v)
            return result
        elif isinstance(value, list):
            return [redact_recursive(item) for item in value]
        elif dataclasses.is_dataclass(value):
            return redact_dataclass_fields(value, redact_recursive)
        else:
            return value

    if isinstance(data, str):
        return redact_pii_string(data)

    return redact_recursive(data)


def redact_pii_string(data: str) -> str:
    analyzer = _get_analyzer()
    anonymizer = _get_anonymizer()
    fields = redact_pii_fields()
    entities = DEFAULT_REDACTED_FIELDS if len(fields) == 0 else fields
    results = analyzer.analyze(text=data, language="en", entities=entities)
    if not results:
        return data

    redacted = anonymizer.anonymize(text=data, analyzer_results=results)
    return redacted.text


def track_pii_redaction_enabled(
    username: str, entity_name: str, project_name: str
) -> None:
    trace_sentry.global_trace_sentry.track_event(
        "pii_redaction_enabled",
        {
            "entity_name": entity_name,
            "project_name": project_name,
        },
        username,
    )
