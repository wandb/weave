"""Unit tests for PII redaction behavior that do not require Presidio installs."""

import importlib
import os
import sys
import types
from contextlib import contextmanager
from unittest import mock

import pytest
from weave.utils import sanitize


@pytest.fixture
def pii_redaction_module(monkeypatch: pytest.MonkeyPatch):
    analyzer_module = types.ModuleType("presidio_analyzer")
    anonymizer_module = types.ModuleType("presidio_anonymizer")
    analyzer_module.AnalyzerEngine = mock.MagicMock(name="AnalyzerEngine")
    anonymizer_module.AnonymizerEngine = mock.MagicMock(name="AnonymizerEngine")

    monkeypatch.setitem(sys.modules, "presidio_analyzer", analyzer_module)
    monkeypatch.setitem(sys.modules, "presidio_anonymizer", anonymizer_module)

    module = importlib.import_module("weave.utils.pii_redaction")
    module = importlib.reload(module)
    yield module

    sys.modules.pop("weave.utils.pii_redaction", None)


@contextmanager
def mock_pii_engines(module):
    analyzer_instance = mock.MagicMock(name="analyzer_instance")
    anonymizer_instance = mock.MagicMock(name="anonymizer_instance")

    def analyze(text: str, language: str, entities: list[str]) -> list[str]:
        results = []
        if "EMAIL_ADDRESS" in entities and "test@example.com" in text:
            results.append("EMAIL_ADDRESS")
        if "PERSON" in entities and "John Doe" in text:
            results.append("PERSON")
        if "PHONE_NUMBER" in entities and "555-0101" in text:
            results.append("PHONE_NUMBER")
        return results

    def anonymize(text: str, analyzer_results: list[str]) -> mock.MagicMock:
        output_text = "[REDACTED]" if analyzer_results else text
        result = mock.MagicMock()
        result.text = output_text
        return result

    analyzer_instance.analyze.side_effect = analyze
    anonymizer_instance.anonymize.side_effect = anonymize

    with (
        mock.patch.object(module, "AnalyzerEngine", return_value=analyzer_instance),
        mock.patch.object(module, "AnonymizerEngine", return_value=anonymizer_instance),
    ):
        yield


def test_redact_pii_string_redacts_default_entities(pii_redaction_module) -> None:
    original = "John Doe test@example.com 555-0101"
    with mock_pii_engines(pii_redaction_module), mock.patch.dict(
        os.environ, {}, clear=True
    ):
        redacted = pii_redaction_module.redact_pii_string(original)

    assert redacted != original
    assert "John Doe" not in redacted
    assert "test@example.com" not in redacted
    assert "555-0101" not in redacted


def test_redact_pii_string_excludes_specific_entities(pii_redaction_module) -> None:
    original = "Contact test@example.com"
    with mock_pii_engines(pii_redaction_module), mock.patch.dict(
        os.environ, {"WEAVE_REDACT_PII_EXCLUDE_FIELDS": "EMAIL_ADDRESS"}, clear=True
    ):
        redacted = pii_redaction_module.redact_pii_string(original)

    assert redacted == original


def test_redact_pii_string_honors_custom_entity_list(pii_redaction_module) -> None:
    email_only_text = "Contact test@example.com"
    person_only_text = "John Doe"

    with mock_pii_engines(pii_redaction_module), mock.patch.dict(
        os.environ, {"WEAVE_REDACT_PII_FIELDS": "PERSON"}, clear=True
    ):
        email_only_redacted = pii_redaction_module.redact_pii_string(email_only_text)
        person_only_redacted = pii_redaction_module.redact_pii_string(person_only_text)

    assert email_only_redacted == email_only_text
    assert person_only_redacted != person_only_text
    assert "John Doe" not in person_only_redacted


def test_redact_pii_redacts_sensitive_keys_and_entities(pii_redaction_module) -> None:
    data = {
        "api_key": "secret-key",
        "message": "John Doe",
        "unchanged": "public-data",
    }

    with mock_pii_engines(pii_redaction_module), mock.patch.dict(
        os.environ, {"WEAVE_REDACT_PII_FIELDS": "PERSON"}, clear=True
    ):
        redacted = pii_redaction_module.redact_pii(data)

    assert redacted["api_key"] == sanitize.REDACTED_VALUE
    assert redacted["message"] != "John Doe"
    assert "John Doe" not in redacted["message"]
    assert redacted["unchanged"] == "public-data"


def test_redact_pii_string_input_is_redacted(pii_redaction_module) -> None:
    original = "John Doe"
    with mock_pii_engines(pii_redaction_module), mock.patch.dict(
        os.environ, {"WEAVE_REDACT_PII_FIELDS": "PERSON"}, clear=True
    ):
        redacted = pii_redaction_module.redact_pii(original)

    assert redacted != original
    assert "John Doe" not in redacted


def test_track_pii_redaction_enabled_tracks_event(pii_redaction_module) -> None:
    with mock.patch.object(
        pii_redaction_module.trace_sentry.global_trace_sentry, "track_event"
    ) as track_event:
        pii_redaction_module.track_pii_redaction_enabled(
            username="test-user",
            entity_name="test-entity",
            project_name="test-project",
        )

    track_event.assert_called_once_with(
        "pii_redaction_enabled",
        {"entity_name": "test-entity", "project_name": "test-project"},
        "test-user",
    )
