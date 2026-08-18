"""Bounded recognizers for the versioned ``pii-v1`` entity set.

The first version covers plausible ASCII email addresses, formatted North
American phone numbers, formatted international phone numbers, compact
``+``-prefixed numbers containing 10 to 15 digits, dashed US SSNs, and
13-to-19-digit card candidates that pass Luhn validation.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

from weave.trace_server.sensitive_data.budget import ScanBudget

PIIEntity = Literal["EMAIL_ADDRESS", "PHONE_NUMBER", "US_SSN", "CREDIT_CARD"]

REPLACEMENT_MARKERS: dict[PIIEntity, str] = {
    "EMAIL_ADDRESS": "<EMAIL_ADDRESS>",
    "PHONE_NUMBER": "<PHONE_NUMBER>",
    "US_SSN": "<US_SSN>",
    "CREDIT_CARD": "<CREDIT_CARD>",
}

_DETECTOR_PRIORITY: dict[PIIEntity, int] = {
    "EMAIL_ADDRESS": 0,
    "US_SSN": 1,
    "CREDIT_CARD": 2,
    "PHONE_NUMBER": 3,
}

_ASCII_DIGIT_RE = re.compile(r"[0-9]")
_MIN_NUMERIC_CANDIDATE_DIGITS = 9
_EMAIL_RE = re.compile(
    r"(?<![A-Za-z0-9.!#$%&'*+/=?^_`{|}~-])"
    r"[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]{1,64}"
    r"@[A-Za-z0-9][A-Za-z0-9.-]{0,251}\.[A-Za-z]{2,63}"
    r"(?![A-Za-z0-9-])",
    re.ASCII,
)
_NUMERIC_RUN_RE = re.compile(r"[+()0-9][+()0-9 .-]{5,}[0-9)]", re.ASCII)
_SSN_RE = re.compile(r"(?<![0-9])([0-9]{3})-([0-9]{2})-([0-9]{4})(?![0-9])")
_CARD_RE = re.compile(r"(?<![0-9])(?:[0-9][ -]?){12,18}[0-9](?![0-9])")
_US_PHONE_RE = re.compile(
    r"(?<![A-Za-z0-9])(?:\+?1[ .-])?"
    r"(?:\([2-9][0-9]{2}\)[ .-]?|[2-9][0-9]{2}[ .-])"
    r"[2-9][0-9]{2}[ .-][0-9]{4}(?![A-Za-z0-9])"
)
_INTERNATIONAL_PHONE_RE = re.compile(
    r"(?<![A-Za-z0-9+])\+[1-9][0-9]{0,2}[ .-]"
    r"(?:[0-9]{2,4}[ .-]){1,3}[0-9]{2,4}(?![A-Za-z0-9])"
)
_COMPACT_INTERNATIONAL_PHONE_RE = re.compile(
    r"(?<![A-Za-z0-9+])\+[1-9][0-9]{9,14}(?![A-Za-z0-9])"
)


@dataclass(frozen=True)
class Detection:
    start: int
    end: int
    entity: PIIEntity


def detect_pii(
    text: str,
    budget: ScanBudget,
    *,
    inspect_string: bool = True,
) -> list[Detection]:
    """Return non-overlapping PII spans without retaining matched text."""
    if inspect_string:
        budget.inspect_string(len(text))
    detections: list[Detection] = []

    if text.find("@") != -1:
        for match in _EMAIL_RE.finditer(text):
            candidate = match.group(0)
            budget.inspect_candidate(len(candidate))
            if _valid_email(candidate) and _absolute_token_boundaries(
                text, match.start(), match.end()
            ):
                _append_detection(
                    detections,
                    Detection(match.start(), match.end(), "EMAIL_ADDRESS"),
                    budget,
                )

    if _ASCII_DIGIT_RE.search(text) is not None:
        for run in _NUMERIC_RUN_RE.finditer(text):
            if not _has_minimum_digits(text, run.start(), run.end()):
                continue
            candidate_length = run.end() - run.start()
            budget.inspect_candidate(candidate_length)
            candidate = run.group(0)
            numeric_detections = _select_non_overlapping(
                _detect_numeric(candidate, run.start(), text)
            )
            for detection in numeric_detections:
                if any(
                    _detections_overlap(detection, existing) for existing in detections
                ):
                    continue
                _append_detection(detections, detection, budget)

    return _select_non_overlapping(detections)


def redact_pii_string(
    text: str,
    budget: ScanBudget,
    *,
    inspect_string: bool = True,
) -> str:
    """Replace supported PII spans with stable typed markers."""
    detections = detect_pii(text, budget, inspect_string=inspect_string)
    if not detections:
        return text

    parts: list[str] = []
    cursor = 0
    for detection in detections:
        parts.append(text[cursor : detection.start])
        parts.append(REPLACEMENT_MARKERS[detection.entity])
        cursor = detection.end
    parts.append(text[cursor:])
    return "".join(parts)


def _valid_email(candidate: str) -> bool:
    local, domain = candidate.rsplit("@", 1)
    if local.startswith(".") or local.endswith(".") or ".." in local:
        return False
    labels = domain.split(".")
    return all(
        1 <= len(label) <= 63 and not label.startswith("-") and not label.endswith("-")
        for label in labels
    )


def _has_minimum_digits(text: str, start: int, end: int) -> bool:
    """Check a numeric run's cheap signal without regex backtracking."""
    position = start
    for _ in range(_MIN_NUMERIC_CANDIDATE_DIGITS):
        match = _ASCII_DIGIT_RE.search(text, position, end)
        if match is None:
            return False
        position = match.end()
    return True


def _detect_numeric(candidate: str, offset: int, text: str) -> list[Detection]:
    # ``pii-v1`` does not accept compact unprefixed phones or SSNs, so a
    # digits-only run can only be a card.
    if candidate.isdecimal():
        if (
            13 <= len(candidate) <= 19
            and _absolute_token_boundaries(text, offset, offset + len(candidate))
            and _valid_card(candidate)
        ):
            return [
                Detection(offset, offset + len(candidate), "CREDIT_CARD"),
            ]
        return []

    detections: list[Detection] = []
    for match in _SSN_RE.finditer(candidate):
        if _valid_ssn(match) and _token_boundaries(text, offset, match):
            detections.append(
                Detection(offset + match.start(), offset + match.end(), "US_SSN"),
            )

    for match in _CARD_RE.finditer(candidate):
        value = match.group(0)
        if (
            _card_boundaries(candidate, match)
            and _token_boundaries(text, offset, match)
            and _valid_card(value)
        ):
            detections.append(
                Detection(offset + match.start(), offset + match.end(), "CREDIT_CARD"),
            )

    for pattern in (
        _US_PHONE_RE,
        _INTERNATIONAL_PHONE_RE,
        _COMPACT_INTERNATIONAL_PHONE_RE,
    ):
        for match in pattern.finditer(candidate):
            if _valid_phone(match.group(0)) and _token_boundaries(text, offset, match):
                detections.append(
                    Detection(
                        offset + match.start(), offset + match.end(), "PHONE_NUMBER"
                    ),
                )
    return detections


def _valid_ssn(match: re.Match[str]) -> bool:
    area, group, serial = match.groups()
    area_number = int(area)
    return (
        area_number not in {0, 666}
        and area_number <= 899
        and group != "00"
        and serial != "0000"
    )


def _valid_card(candidate: str) -> bool:
    digits = "".join(character for character in candidate if character.isdigit())
    if not 13 <= len(digits) <= 19 or len(set(digits)) == 1:
        return False
    checksum = 0
    parity = len(digits) % 2
    for index, character in enumerate(digits):
        digit = int(character)
        if index % 2 == parity:
            digit *= 2
            if digit > 9:
                digit -= 9
        checksum += digit
    return checksum % 10 == 0


def _valid_phone(candidate: str) -> bool:
    digit_count = sum(character.isdigit() for character in candidate)
    return 10 <= digit_count <= 15


def _token_boundaries(text: str, offset: int, match: re.Match[str]) -> bool:
    start = offset + match.start()
    end = offset + match.end()
    return _absolute_token_boundaries(text, start, end)


def _absolute_token_boundaries(text: str, start: int, end: int) -> bool:
    return (start == 0 or not _identifier_character(text[start - 1])) and (
        end == len(text) or not _identifier_character(text[end])
    )


def _identifier_character(character: str) -> bool:
    return character == "_" or (character.isascii() and character.isalnum())


def _card_boundaries(candidate: str, match: re.Match[str]) -> bool:
    start = match.start()
    end = match.end()
    if start >= 2 and candidate[start - 1] in " -" and candidate[start - 2].isdigit():
        return False
    return not (
        end + 1 < len(candidate)
        and candidate[end] in " -"
        and candidate[end + 1].isdigit()
    )


def _append_detection(
    detections: list[Detection], detection: Detection, budget: ScanBudget
) -> None:
    budget.accept_match()
    detections.append(detection)


def _detections_overlap(left: Detection, right: Detection) -> bool:
    return left.start < right.end and right.start < left.end


def _select_non_overlapping(detections: list[Detection]) -> list[Detection]:
    ordered = sorted(
        detections,
        key=lambda detection: (
            detection.start,
            -(detection.end - detection.start),
            _DETECTOR_PRIORITY[detection.entity],
        ),
    )
    selected: list[Detection] = []
    end = -1
    for detection in ordered:
        if detection.start < end:
            continue
        selected.append(detection)
        end = detection.end
    return selected
