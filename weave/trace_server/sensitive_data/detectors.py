"""Bounded recognizers for the versioned ``pii-v1`` entity set.

The first version covers plausible ASCII email addresses, formatted North
American phone numbers, formatted international phone numbers, compact
``+``-prefixed numbers containing 10 to 15 digits, dashed US SSNs, and
13-to-19-digit card candidates that pass Luhn validation.
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from typing import Literal, NamedTuple

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
# One C-level search for "at least 9 digits in the window".
_MIN_NUMERIC_DIGITS_RE = re.compile(
    rf"(?:[0-9][^0-9]*){{{_MIN_NUMERIC_CANDIDATE_DIGITS - 1}}}[0-9]", re.ASCII
)
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
# Numeric candidates contain only digits and these separators.
_DROP_NUMERIC_SEPARATORS = str.maketrans("", "", "+() .-")
# Dot-separated 1-to-63 character labels with no edge hyphens.
_DOMAIN_LABELS_RE = re.compile(
    r"(?:[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?\.)*"
    r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?",
    re.ASCII,
)
_IDENTIFIER_CHARACTERS = frozenset(
    "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_"
)


class Detection(NamedTuple):
    start: int
    end: int
    entity: PIIEntity


def detect_pii(text: str) -> list[Detection]:
    """Return non-overlapping PII spans without retaining matched text."""
    return list(_iter_detections(text))


def _iter_detections(text: str) -> Iterator[Detection]:
    """Yield accepted detections in ascending order without collecting them.

    Emails and numeric runs each ascend and never self-overlap, so a two-stream
    merge replaces collecting and sorting every detection; a numeric detection
    overlapping the pending email is dropped, keeping email priority.
    """
    emails = _iter_email_detections(text) if text.find("@") != -1 else iter(())
    numerics = (
        _iter_numeric_detections(text)
        if _ASCII_DIGIT_RE.search(text) is not None
        else iter(())
    )
    email = next(emails, None)
    for detection in numerics:
        while email is not None and email.end <= detection.start:
            yield email
            email = next(emails, None)
        if email is not None and email.start < detection.end:
            continue
        yield detection
    while email is not None:
        yield email
        email = next(emails, None)


def _iter_email_detections(text: str) -> Iterator[Detection]:
    for match in _EMAIL_RE.finditer(text):
        if _valid_email(match.group(0)) and _absolute_token_boundaries(
            text, match.start(), match.end()
        ):
            yield Detection(match.start(), match.end(), "EMAIL_ADDRESS")


def _iter_numeric_detections(text: str) -> Iterator[Detection]:
    for run in _NUMERIC_RUN_RE.finditer(text):
        if not _has_minimum_digits(text, run.start(), run.end()):
            continue
        yield from _select_non_overlapping(
            _detect_numeric(run.group(0), run.start(), text)
        )


def redact_pii_string(text: str) -> str:
    """Replace supported PII spans with stable typed markers."""
    parts: list[str] = []
    cursor = 0
    for detection in _iter_detections(text):
        parts.append(text[cursor : detection.start])
        parts.append(REPLACEMENT_MARKERS[detection.entity])
        cursor = detection.end
    if not parts:
        return text
    parts.append(text[cursor:])
    return "".join(parts)


def _valid_email(candidate: str) -> bool:
    local, domain = candidate.rsplit("@", 1)
    if local.startswith(".") or local.endswith(".") or ".." in local:
        return False
    return _DOMAIN_LABELS_RE.fullmatch(domain) is not None


def _has_minimum_digits(text: str, start: int, end: int) -> bool:
    """Check a numeric run's cheap signal without regex backtracking."""
    return _MIN_NUMERIC_DIGITS_RE.search(text, start, end) is not None


def _detect_numeric(candidate: str, offset: int, text: str) -> list[Detection]:
    # A digits-only run can only be a card under ``pii-v1``.
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

    # Skip sub-detectors whose required characters are absent.
    detections: list[Detection] = []
    if "-" in candidate:
        for match in _SSN_RE.finditer(candidate):
            if _valid_ssn(match) and _token_boundaries(text, offset, match):
                detections.append(
                    Detection(offset + match.start(), offset + match.end(), "US_SSN"),
                )

    if len(candidate) >= 13:
        for match in _CARD_RE.finditer(candidate):
            value = match.group(0)
            if (
                _card_boundaries(candidate, match)
                and _token_boundaries(text, offset, match)
                and _valid_card(value)
            ):
                detections.append(
                    Detection(
                        offset + match.start(), offset + match.end(), "CREDIT_CARD"
                    ),
                )

    patterns = (
        (_US_PHONE_RE, _INTERNATIONAL_PHONE_RE, _COMPACT_INTERNATIONAL_PHONE_RE)
        if "+" in candidate
        else (_US_PHONE_RE,)
    )
    for pattern in patterns:
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


_LUHN_DOUBLED = (0, 2, 4, 6, 8, 1, 3, 5, 7, 9)


def _valid_card(candidate: str) -> bool:
    digits = candidate.translate(_DROP_NUMERIC_SEPARATORS)
    if not 13 <= len(digits) <= 19 or len(set(digits)) == 1:
        return False
    checksum = 0
    parity = len(digits) % 2
    for index, character in enumerate(digits):
        digit = ord(character) - 48
        checksum += _LUHN_DOUBLED[digit] if index % 2 == parity else digit
    return checksum % 10 == 0


def _valid_phone(candidate: str) -> bool:
    return 10 <= len(candidate.translate(_DROP_NUMERIC_SEPARATORS)) <= 15


def _token_boundaries(text: str, offset: int, match: re.Match[str]) -> bool:
    start = offset + match.start()
    end = offset + match.end()
    return _absolute_token_boundaries(text, start, end)


def _absolute_token_boundaries(text: str, start: int, end: int) -> bool:
    return (start == 0 or not _identifier_character(text[start - 1])) and (
        end == len(text) or not _identifier_character(text[end])
    )


def _identifier_character(character: str) -> bool:
    return character in _IDENTIFIER_CHARACTERS


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


def _detections_overlap(left: Detection, right: Detection) -> bool:
    return left.start < right.end and right.start < left.end


def _select_non_overlapping(detections: list[Detection]) -> list[Detection]:
    if len(detections) < 2:
        return detections
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
