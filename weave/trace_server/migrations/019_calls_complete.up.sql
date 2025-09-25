CREATE TABLE calls_complete (
    id              String,
    project_id      String,
    created_at      DateTime64(3) DEFAULT now64(3),

    trace_id        String,
    op_name         String,
    started_at      DateTime64(6),
    ended_at        DateTime64(6),

    deleted_at      Nullable(DateTime64(3)) DEFAULT NULL,
    parent_id       Nullable(String),
    display_name    Nullable(String) DEFAULT NULL,
    
    attributes_dump Nullable(String),
    inputs_dump     Nullable(String),
    input_refs      Array(String),
    output_dump     Nullable(String),
    summary_dump    Nullable(String),
    exception       Nullable(String),
    output_refs     Array(String),

    wb_user_id      Nullable(String),
    wb_run_id       Nullable(String),
    wb_run_step     Nullable(UInt64) DEFAULT NULL,

    thread_id       Nullable(String) DEFAULT NULL,
    turn_id         Nullable(String) DEFAULT NULL,

    INDEX idx_wb_run_id wb_run_id TYPE set(100) GRANULARITY 1,

    PROJECTION projection_calls_by_op_name (
        SELECT *
        ORDER BY project_id, op_name, started_at
    ),

    PROJECTION projection_calls_by_trace_id (
        SELECT *
        ORDER BY project_id, trace_id, started_at
    )
) ENGINE = MergeTree
ORDER BY (project_id, started_at, id);
