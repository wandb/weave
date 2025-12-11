-- Ensure the correct ZK path with shard macro is used for the replicated table
SET default_replica_path = '/clickhouse/{cluster}/tables/{shard}/{database}/{table}';

DETACH TABLE calls_complete;
ATTACH TABLE calls_complete AS REPLICATED;
SYSTEM RESTORE REPLICA calls_complete;
