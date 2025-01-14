import json

from presidio_analyzer import AnalyzerEngine
from presidio_anonymizer import AnonymizerEngine

from weave.trace.settings import should_redact_pii


def redact_pii(data):
    analyzer = AnalyzerEngine()
    anonymizer = AnonymizerEngine()

    def redact_value(value):
        if isinstance(value, str):
            results = analyzer.analyze(text=value, language='en')  # TODO: support more languages.
            anonymized_text = anonymizer.anonymize(text=value, analyzer_results=results)
            return anonymized_text.text
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
