# Weave Trace Server Migrations

## Squash Migration

The file `weave/trace_server/squash_migration.sql` contains a squashed version of
all migrations. When the migrator detects a fresh (empty) database, it applies the
squash file instead of running every individual migration sequentially. This makes
fresh installations significantly faster.

### Adding a new migration

When you add a new migration file (e.g., `029_my_change.up.sql`):

1. Create your `.up.sql` and `.down.sql` files as usual.
2. **Update `squash_migration.sql`** to reflect the final schema state including
   your change. The squash file should produce an identical schema to running all
   migrations sequentially from scratch.
3. **Update `SQUASH_MIGRATION_VERSION`** in `clickhouse_trace_server_migrator.py`
   to match the new max migration number.
4. Run the test `test_squash_migration_matches_sequential` to verify the squash
   stays in sync:
   ```
   nox --no-install -e "tests-3.12(shard='trace_server')" -- \
     tests/trace_server_migrator/test_migrator_functional.py::test_squash_migration_matches_sequential
   ```

### Rules

- The squash file must produce **exactly** the same tables, columns, engines,
  indexes, and views as running all individual migrations on a fresh database.
- The squash file should NOT include data-seeding statements (e.g., cost data
  from migration 006). Data seeding is handled by the post-migration hook.
- The squash file should NOT include `MATERIALIZE INDEX` or `MATERIALIZE COLUMN`
  commands, since the tables are brand new and have no existing data to reindex.
- The squash file should NOT include intermediate/temporary tables from migration
  upgrade procedures (e.g., `calls_complete_old` from the v1-to-v2 migration).
