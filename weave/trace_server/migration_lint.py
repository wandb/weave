"""Static safety linter for ClickHouse migration SQL.

Flags anti-patterns that make a migration unsafe to retry after a partial
failure: non-idempotent DDL (CREATE/DROP/ADD without IF [NOT] EXISTS) and
irreversible/destructive statements placed before further mutating steps.
"""

import os
import re
from dataclasses import dataclass

from weave.trace_server.clickhouse.utilities import split_migration_sql


@dataclass(frozen=True)
class LintFinding:
    version: int
    file: str
    rule: str
    message: str


def lint_migration_sql(file_name: str, sql: str) -> list[LintFinding]:
    """Lint a single migration's SQL text for idempotency and op ordering."""
    version = _parse_version(file_name)
    findings: list[LintFinding] = []
    statements = split_migration_sql(sql)

    seen_irreversible = False
    for statement in statements:
        normalized = _normalize(statement)
        head = _leading_keyword(normalized)

        if head in {"CREATE", "DROP", "ALTER"}:
            if _UNGUARDED_CREATE_RE.search(normalized):
                findings.append(
                    LintFinding(
                        version,
                        file_name,
                        "R1",
                        f"CREATE without IF NOT EXISTS: {_preview(statement)}",
                    )
                )
            if _UNGUARDED_DROP_RE.search(normalized):
                findings.append(
                    LintFinding(
                        version,
                        file_name,
                        "R2",
                        f"DROP without IF EXISTS: {_preview(statement)}",
                    )
                )
            if _UNGUARDED_ADD_RE.search(normalized):
                findings.append(
                    LintFinding(
                        version,
                        file_name,
                        "R3",
                        f"ADD without IF NOT EXISTS: {_preview(statement)}",
                    )
                )

        # R4 ordering only considers real DDL statements; a DDL keyword inside a
        # string literal (e.g. an INSERT payload) must not move this state.
        if head in {"ALTER", "CREATE", "DROP", "RENAME"}:
            if seen_irreversible and _MUTATING_RE.search(normalized):
                findings.append(
                    LintFinding(
                        version,
                        file_name,
                        "R4",
                        f"mutating statement follows an irreversible op: {_preview(statement)}",
                    )
                )
            if _IRREVERSIBLE_RE.search(normalized):
                seen_irreversible = True

    return findings


def lint_migration_dir(
    migration_dir: str, min_enforced_version: int
) -> list[LintFinding]:
    """Lint migrations in a dir; R5 (down pairing) applies to every version, R1-R4 only past min_enforced_version."""
    findings: list[LintFinding] = []
    for file_name in os.listdir(migration_dir):
        if not file_name.endswith(".up.sql"):
            continue
        version = _parse_version(file_name)

        down_name = file_name[: -len(".up.sql")] + ".down.sql"
        if not os.path.exists(os.path.join(migration_dir, down_name)):
            findings.append(
                LintFinding(
                    version,
                    file_name,
                    "R5",
                    f"missing matching down migration: {down_name}",
                )
            )

        if version <= min_enforced_version:
            continue
        with open(os.path.join(migration_dir, file_name), encoding="utf-8") as f:
            sql = f.read()
        findings.extend(lint_migration_sql(file_name, sql))

    return sorted(findings, key=lambda f: (f.version, f.rule, f.message))


def _parse_version(file_name: str) -> int:
    base = os.path.basename(file_name)
    return int(base.split("_", 1)[0], 10)


def _normalize(statement: str) -> str:
    return re.sub(r"\s+", " ", statement).strip().upper()


def _leading_keyword(normalized: str) -> str:
    return normalized.split(" ", 1)[0] if normalized else ""


def _preview(statement: str) -> str:
    collapsed = re.sub(r"\s+", " ", statement).strip()
    return collapsed[:80]


# Idempotency rules match per clause: each CREATE/DROP/ADD object must be
# immediately followed by its IF [NOT] EXISTS guard, so a partially guarded
# compound ALTER still fires on the unguarded clause.
_UNGUARDED_CREATE_RE = re.compile(
    r"\bCREATE\s+(?:TABLE|(?:MATERIALIZED\s+)?VIEW|DICTIONARY)\s+(?!IF\s+NOT\s+EXISTS)"
)
_UNGUARDED_DROP_RE = re.compile(
    r"\bDROP\s+(?:TABLE|VIEW|DICTIONARY|COLUMN|INDEX)\s+(?!IF\s+EXISTS)"
)
_UNGUARDED_ADD_RE = re.compile(r"\bADD\s+(?:COLUMN|INDEX)\s+(?!IF\s+NOT\s+EXISTS)")

# A guarded DROP is safe to retry, so only unguarded drops and RENAME COLUMN
# are irreversible for ordering purposes.
_IRREVERSIBLE_RE = re.compile(
    r"\bRENAME\s+COLUMN\b"
    r"|\bDROP\s+COLUMN\s+(?!IF\s+EXISTS)"
    r"|\bDROP\s+TABLE\s+(?!IF\s+EXISTS)"
)
_MUTATING_RE = re.compile(r"\bCREATE\b|\bADD\b|\bMODIFY\b")
