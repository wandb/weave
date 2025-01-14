import json

from presidio_analyzer import AnalyzerEngine
from presidio_anonymizer import AnonymizerEngine

from weave.trace.settings import should_redact_pii


def redact_pii(data):
    if not should_redact_pii():
        return data

    def redact_value(value):
        if isinstance(value, str):
            # Analyze and anonymize the string
            results = analyzer.analyze(text=value, language='en')  # TODO: support more languages.
            anonymized_text = anonymizer.anonymize(text=value, analyzer_results=results)
            return anonymized_text.text
        elif isinstance(value, dict):
            return {k: redact_value(v) for k, v in value.items()}
        elif isinstance(value, list):
            return [redact_value(item) for item in value]
        else:
            return value

    # Initialize the Presidio Analyzer and Anonymizer
    analyzer = AnalyzerEngine()
    anonymizer = AnonymizerEngine()

    # Check if the input is a string or a dictionary
    if isinstance(data, str):
        # If it's a string, treat it as a JSON string and parse it
        try:
            data = json.loads(data)
        except json.JSONDecodeError:
            # If it's not a valid JSON, just redact the string itself
            return redact_value(data)

    # Redact PII from the dictionary
    return {k: redact_value(v) for k, v in data.items()}
