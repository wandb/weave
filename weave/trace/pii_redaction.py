import json

from presidio_analyzer import AnalyzerEngine
from presidio_anonymizer import AnonymizerEngine

from weave.trace.settings import redact_pii_fields

DEFAULT_REDACTED_FIELDS = [
    "CREDIT_CARD",
    "CRYPTO",
    "EMAIL_ADDRESS",
    "IBAN_CODE",
    "IP_ADDRESS",
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


def redact_pii(data):
    analyzer = AnalyzerEngine()
    anonymizer = AnonymizerEngine()

    def redact_value(value):
        if isinstance(value, str):
            fields = redact_pii_fields()
            entities = DEFAULT_REDACTED_FIELDS if len(fields) == 0 else fields
            results = analyzer.analyze(text=value, language="en", entities=entities)
            redacted = anonymizer.anonymize(text=value, analyzer_results=results)
            return redacted.text
        elif isinstance(value, dict):
            return {k: redact_value(v) for k, v in value.items()}
        elif isinstance(value, list):
            return [redact_value(item) for item in value]
        else:
            return value

    if isinstance(data, str):
        try:
            data = json.loads(data)
        except json.JSONDecodeError:
            return redact_value(data)

    return {k: redact_value(v) for k, v in data.items()}
