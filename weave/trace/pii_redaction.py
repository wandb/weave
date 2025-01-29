import json
from typing import Any

from presidio_analyzer import AnalyzerEngine
from presidio_anonymizer import AnonymizerEngine

from weave.trace.settings import redact_pii_fields

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


def redact_pii(
    data: dict[str, Any],
) -> dict[str, Any]:
    analyzer = AnalyzerEngine()
    anonymizer = AnonymizerEngine()
    fields = redact_pii_fields()
    entities = DEFAULT_REDACTED_FIELDS if len(fields) == 0 else fields

    def redact_recursive(value: Any) -> Any:
        if isinstance(value, str):
            results = analyzer.analyze(text=value, language="en", entities=entities)
            redacted = anonymizer.anonymize(text=value, analyzer_results=results)
            return redacted.text
        elif isinstance(value, dict):
            return {k: redact_recursive(v) for k, v in value.items()}
        elif isinstance(value, list):
            return [redact_recursive(item) for item in value]
        else:
            return value

    if isinstance(data, str):
        try:
            data = json.loads(data)
        except json.JSONDecodeError:
            pass

    return redact_recursive(data)
