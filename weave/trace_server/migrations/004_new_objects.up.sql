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
