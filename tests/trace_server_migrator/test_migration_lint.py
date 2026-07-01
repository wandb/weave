"""Pure-python tests for the migration safety linter (no ClickHouse required)."""

import os

from weave.trace_server.migration_lint import (
    lint_migration_dir,
    lint_migration_sql,
)

_PROD_MIGRATION_DIR = os.path.abspath(
    os.path.join(
        os.path.dirname(__file__), "..", "..", "weave", "trace_server", "migrations"
    )
)

# Highest version already shipped when the linter landed. Migrations at or below
# this are grandfathered; anything newer must pass every rule.
_GRANDFATHERED_THROUGH_VERSION = 35


def test_r1_create_without_if_not_exists():
    bad = "CREATE TABLE foo (a String) ENGINE = MergeTree() ORDER BY a;"
    rules = {f.rule for f in lint_migration_sql("100_x.up.sql", bad)}
    assert "R1" in rules

    good = "CREATE TABLE IF NOT EXISTS foo (a String) ENGINE = MergeTree() ORDER BY a;"
    assert lint_migration_sql("100_x.up.sql", good) == []


def test_r2_drop_without_if_exists():
    bad = "DROP TABLE foo;"
    rules = {f.rule for f in lint_migration_sql("100_x.up.sql", bad)}
    assert "R2" in rules

    good = "DROP TABLE IF EXISTS foo;"
    assert lint_migration_sql("100_x.up.sql", good) == []


def test_r3_add_column_without_if_not_exists():
    bad = "ALTER TABLE foo ADD COLUMN bar String;"
    rules = {f.rule for f in lint_migration_sql("100_x.up.sql", bad)}
    assert "R3" in rules

    good = "ALTER TABLE foo ADD COLUMN IF NOT EXISTS bar String;"
    assert lint_migration_sql("100_x.up.sql", good) == []


def test_r4_irreversible_before_mutating():
    bad = (
        "ALTER TABLE foo RENAME COLUMN a TO b;\n"
        "ALTER TABLE foo ADD COLUMN IF NOT EXISTS c String;"
    )
    rules = {f.rule for f in lint_migration_sql("100_x.up.sql", bad)}
    assert "R4" in rules

    good = (
        "ALTER TABLE foo ADD COLUMN IF NOT EXISTS c String;\n"
        "ALTER TABLE foo RENAME COLUMN a TO b;"
    )
    assert lint_migration_sql("100_x.up.sql", good) == []


def test_compound_alter_flags_only_unguarded_clause():
    bad = "ALTER TABLE foo ADD COLUMN IF NOT EXISTS a String, ADD COLUMN b String;"
    rules = {f.rule for f in lint_migration_sql("100_x.up.sql", bad)}
    assert "R3" in rules

    good = (
        "ALTER TABLE foo "
        "ADD COLUMN IF NOT EXISTS a String, ADD COLUMN IF NOT EXISTS b String;"
    )
    assert lint_migration_sql("100_x.up.sql", good) == []


def test_guarded_drop_then_recreate_is_clean():
    sql = (
        "DROP TABLE IF EXISTS foo;\n"
        "CREATE TABLE IF NOT EXISTS foo (a String) ENGINE = MergeTree() ORDER BY a;"
    )
    assert lint_migration_sql("100_x.up.sql", sql) == []


def test_ddl_keywords_in_string_literal_not_flagged():
    sql = "INSERT INTO audit VALUES ('CREATE TABLE run', 'DROP COLUMN x');"
    assert lint_migration_sql("100_x.up.sql", sql) == []


def test_r4_ignores_ddl_keywords_in_string_literals():
    # An INSERT payload carrying a DDL keyword must not trip the ordering state
    # and falsely flag a following guarded statement.
    sql = (
        "INSERT INTO audit VALUES ('DROP TABLE x');\n"
        "ALTER TABLE foo ADD COLUMN IF NOT EXISTS c String;"
    )
    assert lint_migration_sql("100_x.up.sql", sql) == []


def test_dir_walker_flags_known_029_violations():
    findings = lint_migration_dir(_PROD_MIGRATION_DIR, min_enforced_version=0)
    rules_029 = {f.rule for f in findings if f.version == 29}
    assert "R1" in rules_029, findings
    assert "R4" in rules_029, findings


def test_no_new_migrations_violate_rules():
    findings = lint_migration_dir(
        _PROD_MIGRATION_DIR, min_enforced_version=_GRANDFATHERED_THROUGH_VERSION
    )
    assert findings == [], findings
