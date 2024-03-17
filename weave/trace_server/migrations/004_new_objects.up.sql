CREATE TABLE objects
(
    entity String,
    project String,
    name String,
    created_at DateTime64 DEFAULT now64(),
    type String,
    refs Array(String),
    val String,
    digest String
) 
ENGINE = MergeTree() 
ORDER BY (entity, project, type, name, created_at);

CREATE VIEW objects_deduped AS
SELECT
    entity,
    project,
    name,
    created_at,
    type,
    refs,
    val,
    digest,
    row_number() OVER (PARTITION BY entity, project, type, name ORDER BY created_at ASC) AS _version_index_plus_1,
    _version_index_plus_1 - 1 AS version_index,
    count(*) OVER (PARTITION BY entity, project, type, name) as version_count,
    if(_version_index_plus_1 = version_count, 1, 0) AS is_latest
FROM (
    SELECT *,
           row_number() OVER (PARTITION BY entity, project, type, name, digest ORDER BY created_at ASC) AS rn
    FROM objects
) WHERE rn = 1
WINDOW w AS (PARTITION BY entity, project, type, name ORDER BY created_at ASC)
ORDER BY entity, project, type, name, created_at;

CREATE TABLE tables
(
    id UUID,
    created_at DateTime64 DEFAULT now64(),
    transaction_ids Array(UUID)
) 
ENGINE = MergeTree() 
ORDER BY (id);

CREATE TABLE table_transactions
(
    tx_id UUID,
    id UUID,
    item_version UUID,
    type String,
    created_at DateTime64 DEFAULT now64(),
    tx_order UInt32,
    refs Array(String),
    val Nullable(String),
    val_hash Nullable(String) MATERIALIZED MD5(val)
) 
ENGINE = MergeTree() 
ORDER BY (tx_id, tx_order);
