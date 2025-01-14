ALTER TABLE object_versions
    DROP COLUMN wb_user_id;

CREATE OR REPLACE VIEW object_versions_deduped as
    SELECT project_id,
        object_id,
        created_at,
        deleted_at,
        kind,
        base_object_class,
        refs,
        -- **** Remove wb_user_id from the view ****
        val_dump,
        digest,
        if (kind = 'op', 1, 0) AS is_op,
        row_number() OVER (
            PARTITION BY project_id,
            kind,
            object_id
            ORDER BY created_at ASC
        ) AS _version_index_plus_1,
        _version_index_plus_1 - 1 AS version_index,
        count(*) OVER (PARTITION BY project_id, kind, object_id) as version_count,
        if(_version_index_plus_1 = version_count, 1, 0) AS is_latest
    FROM (
            SELECT *,
                row_number() OVER (
                    PARTITION BY project_id,
                    kind,
                    object_id,
                    digest
                    ORDER BY created_at ASC
                ) AS rn
            FROM object_versions
        )
    WHERE rn = 1 WINDOW w AS (
            PARTITION BY project_id,
            kind,
            object_id
            ORDER BY created_at ASC
        )
    ORDER BY project_id,
        kind,
        object_id,
        created_at;

ALTER TABLE object_versions_stats
    DROP COLUMN wb_user_id;