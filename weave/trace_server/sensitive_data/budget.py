"""Request-wide work limits for sensitive-data scans."""

from dataclasses import dataclass

from weave.trace_server.errors import RequestTooLarge

DEFAULT_MAX_STRUCTURE_DEPTH = 64
DEFAULT_MAX_CANDIDATE_CHARACTERS = 512
DEFAULT_MAX_TOTAL_CHARACTERS = 16 * 1024 * 1024
DEFAULT_MAX_DETAILED_CHARACTERS = 4 * 1024 * 1024


@dataclass
class ScanBudget:
    """Mutable counters shared by every protected field in one write request.

    There is deliberately no accepted-match limit: every match spans several
    characters, so the character budgets already bound match count, and a
    match limit rejects exactly the PII-dense content the scan exists to
    protect.
    """

    max_structure_depth: int = DEFAULT_MAX_STRUCTURE_DEPTH
    max_candidate_characters: int = DEFAULT_MAX_CANDIDATE_CHARACTERS
    max_total_characters: int = DEFAULT_MAX_TOTAL_CHARACTERS
    max_detailed_characters: int = DEFAULT_MAX_DETAILED_CHARACTERS
    total_characters: int = 0
    detailed_characters: int = 0

    def inspect_string(self, length: int) -> None:
        self.total_characters += length
        if self.total_characters > self.max_total_characters:
            raise RequestTooLarge("Sensitive-data scan character limit exceeded")

    def inspect_candidate(self, length: int) -> None:
        if length > self.max_candidate_characters:
            raise RequestTooLarge("Sensitive-data candidate length limit exceeded")
        self.detailed_characters += length
        if self.detailed_characters > self.max_detailed_characters:
            raise RequestTooLarge("Sensitive-data detailed scan limit exceeded")

    def check_depth(self, depth: int) -> None:
        if depth > self.max_structure_depth:
            raise RequestTooLarge("Sensitive-data nesting limit exceeded")
