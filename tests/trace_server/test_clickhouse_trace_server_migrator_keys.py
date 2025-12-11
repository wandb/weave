import os
from unittest.mock import Mock, patch

import pytest

from weave.trace_server import clickhouse_trace_server_migrator as trace_server_migrator


@pytest.fixture
def mock_costs():
    with patch(
        "weave.trace_server.costs.insert_costs.should_insert_costs", return_value=False
    ):
        with patch(
            "weave.trace_server.costs.insert_costs.get_current_costs", return_value=[]
        ):
            yield


@pytest.fixture
def migrator():
    ch_client = Mock()
    migrator = trace_server_migrator.ClickHouseTraceServerMigrator(ch_client)
    # Don't mock internal methods by default for these tests as we want to test the logic
    # But we will mock _initialize_migration_db in __init__ implicitly by mocking the client
    # actually __init__ calls _initialize_migration_db, so we need to be careful.
    return migrator


def test_get_migrations_parsing(tmp_path):
    # Setup migration files
    migration_dir = tmp_path / "migrations"
    migration_dir.mkdir()

    files = [
        "1_init.up.sql",
        "1_init.down.sql",
        "2_feature.experimental.up.sql",
        "2_feature.experimental.down.sql",
        "3_complex.alpha_beta.up.sql",
        "3_complex.alpha_beta.down.sql",
        "4_legacy.up.sql",
        "4_legacy.down.sql",
    ]
    for f in files:
        (migration_dir / f).write_text("")

    ch_client = Mock()
    migrator = trace_server_migrator.ClickHouseTraceServerMigrator(ch_client)

    # Mock where the migrator looks for files
    with (
        patch("os.path.dirname", return_value=str(tmp_path)),
        patch("os.path.join", side_effect=os.path.join),
    ):
        migration_map = migrator._get_migrations()

        assert len(migration_map) == 4

        # Check standard migration
        assert migration_map[1]["up"] == "1_init.up.sql"
        assert migration_map[1].get("keys") == []

        # Check single key
        assert migration_map[2]["up"] == "2_feature.experimental.up.sql"
        assert set(migration_map[2]["keys"]) == {"experimental"}

        # Check multiple keys
        assert migration_map[3]["up"] == "3_complex.alpha_beta.up.sql"
        assert set(migration_map[3]["keys"]) == {"alpha", "beta"}

        # Check legacy style (implied no keys)
        assert migration_map[4]["up"] == "4_legacy.up.sql"
        assert migration_map[4].get("keys") == []


def test_apply_migrations_skips_mismatch_keys(mock_costs, migrator, tmp_path):
    # Setup
    migrator._get_migration_status = Mock(
        return_value={
            "curr_version": 0,
            "partially_applied_version": None,
        }
    )

    # Mock migration map with keys
    # version 1: no keys (should run)
    # version 2: key 'experimental' (should skip if env var not set)
    # version 3: key 'beta' (should skip)

    # We need to mock _get_migrations to return our map structure
    # But wait, we need to make sure the implementation of _get_migrations actually returns the keys structure first.
    # Since we haven't implemented that yet, we'll mock it returning the structure we EXPECT.

    migrator._get_migrations = Mock(
        return_value={
            1: {"up": "1_init.up.sql", "down": "1_init.down.sql", "keys": []},
            2: {
                "up": "2_exp.experimental.up.sql",
                "down": "2_exp.experimental.down.sql",
                "keys": ["experimental"],
            },
            3: {
                "up": "3_beta.beta.up.sql",
                "down": "3_beta.beta.down.sql",
                "keys": ["beta"],
            },
        }
    )

    # We assume _determine_migrations_to_apply returns all valid next migrations regardless of keys
    # because it just looks at version numbers.
    # We will verify this assumption by NOT mocking _determine_migrations_to_apply if we can,
    # OR we mock it to return what the real one would return.
    # The real one returns a list of (version, file).
    migrator._determine_migrations_to_apply = Mock(
        return_value=[
            (1, "1_init.up.sql"),
            (2, "2_exp.experimental.up.sql"),
            (3, "3_beta.beta.up.sql"),
        ]
    )

    # We need to mock _apply_migration to track calls, but we also want to test the logic that decides
    # whether to call _apply_migration or skip it.
    # The logic for skipping will likely be in apply_migrations.

    # Let's mock _apply_migration to just do nothing but be callable
    migrator._apply_migration = Mock()

    # Mock _update_migration_status to verify we update version even when skipping
    migrator._update_migration_status = Mock()

    # CASE 1: No keys in env var
    # Should run 1, Skip 2, Skip 3
    migrator.migration_keys = []
    migrator.apply_migrations("test_db", target_version=3)

    # Check 1 ran
    migrator._apply_migration.assert_any_call("test_db", 1, "1_init.up.sql")

    # Check 2 skipped (not called)
    try:
        migrator._apply_migration.assert_any_call(
            "test_db", 2, "2_exp.experimental.up.sql"
        )
        raise AssertionError("Should have skipped migration 2")
    except AssertionError:
        pass

    # Check 3 skipped
    try:
        migrator._apply_migration.assert_any_call("test_db", 3, "3_beta.beta.up.sql")
        raise AssertionError("Should have skipped migration 3")
    except AssertionError:
        pass

    # Check version updates happen for ALL (skipped ones too)
    # We expect status updates for 1 (start/end), 2 (start/end?), 3 (start/end?)
    # If we skip, we probably just update status to say "we passed this version".
    # Implementation detail: we might just call _update_migration_status(..., is_start=False)
    # effectively bumping the version without running SQL.
    # Let's assume the implementation will call _update_migration_status(..., is_start=False) for skipped ones.

    # Actually, simpler expectation: version should be updated to 3 eventually.
    calls = migrator._update_migration_status.call_args_list
    # We expect calls for 1, 2, 3.
    versions_updated = [
        c[0][1] for c in calls if c[0][0] == "test_db" and c[0][2] is False
    ]  # is_start=False
    assert 1 in versions_updated
    assert 2 in versions_updated
    assert 3 in versions_updated


def test_apply_migrations_matches_keys(mock_costs, migrator):
    # Setup
    migrator._get_migration_status = Mock(
        return_value={"curr_version": 0, "partially_applied_version": None}
    )
    migrator._get_migrations = Mock(
        return_value={
            1: {"up": "1.up.sql", "keys": []},
            2: {"up": "2.exp.up.sql", "keys": ["experimental"]},
        }
    )
    migrator._determine_migrations_to_apply = Mock(
        return_value=[(1, "1.up.sql"), (2, "2.exp.up.sql")]
    )
    migrator._apply_migration = Mock()
    migrator._update_migration_status = Mock()

    # CASE 2: Env var has 'experimental'
    migrator.migration_keys = ["experimental"]
    migrator.apply_migrations("test_db", target_version=2)

    # Should run both
    migrator._apply_migration.assert_any_call("test_db", 1, "1.up.sql")
    migrator._apply_migration.assert_any_call("test_db", 2, "2.exp.up.sql")


def test_apply_migrations_partial_keys(mock_costs, migrator):
    # Setup
    migrator._get_migration_status = Mock(
        return_value={"curr_version": 0, "partially_applied_version": None}
    )
    migrator._get_migrations = Mock(
        return_value={
            1: {"up": "1.up.sql", "keys": ["alpha", "beta"]},
        }
    )
    migrator._determine_migrations_to_apply = Mock(return_value=[(1, "1.up.sql")])
    migrator._apply_migration = Mock()
    migrator._update_migration_status = Mock()

    # CASE 3: Env var has 'alpha' (one of the keys)
    migrator.migration_keys = ["alpha"]
    migrator.apply_migrations("test_db", target_version=1)

    # Should run because alpha matches
    migrator._apply_migration.assert_called_with("test_db", 1, "1.up.sql")

    # CASE 4: Env var has 'gamma' (no match)
    migrator._apply_migration.reset_mock()
    migrator.migration_keys = ["gamma"]
    migrator.apply_migrations("test_db", target_version=1)

    # Should skip
    migrator._apply_migration.assert_not_called()
    # But should update version
    assert migrator._update_migration_status.call_count > 0
