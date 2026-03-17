CREATE TABLE genai_spans (
    -- Core span identity
    project_id          String,
    trace_id            String,
    span_id             String,
    parent_span_id      String DEFAULT '',
    span_name           String,
    span_kind           Enum8('UNSPECIFIED'=0,'INTERNAL'=1,'SERVER'=2,'CLIENT'=3,'PRODUCER'=4,'CONSUMER'=5),

    -- Timestamps
    started_at          DateTime64(6),
    ended_at            DateTime64(6) DEFAULT toDateTime64(0, 6),
    created_at          DateTime64(3) DEFAULT now64(3),

    -- Status
    status_code         Enum8('UNSET'=0,'OK'=1,'ERROR'=2),
    status_message      String DEFAULT '',

    -- GenAI classification (extracted from semconv)
    operation_name      LowCardinality(String) DEFAULT '',
    provider_name       LowCardinality(String) DEFAULT '',

    -- Agent info
    agent_name          String DEFAULT '',
    agent_id            String DEFAULT '',
    agent_description   String DEFAULT '',
    agent_version       String DEFAULT '',

    -- Model info
    request_model       String DEFAULT '',
    response_model      String DEFAULT '',
    response_id         String DEFAULT '',

    -- Token usage
    input_tokens        UInt64 DEFAULT 0,
    output_tokens       UInt64 DEFAULT 0,
    total_tokens        UInt64 DEFAULT 0,

    -- Conversation / session
    conversation_id     String DEFAULT '',

    -- Tool info
    tool_name           String DEFAULT '',
    tool_type           LowCardinality(String) DEFAULT '',
    tool_call_id        String DEFAULT '',
    tool_description    String DEFAULT '',

    -- Response
    finish_reasons      Array(String),

    -- Request params
    request_temperature Float64 DEFAULT 0,
    request_max_tokens  UInt64 DEFAULT 0,
    request_top_p       Float64 DEFAULT 0,

    -- Content (JSON blobs, potentially large)
    input_messages      String DEFAULT '',
    output_messages     String DEFAULT '',
    system_instructions String DEFAULT '',
    tool_call_arguments String DEFAULT '',
    tool_call_result    String DEFAULT '',

    -- Raw dumps for debugging / future extraction
    attributes_dump     String DEFAULT '',
    events_dump         String DEFAULT '',
    resource_dump       String DEFAULT '',

    -- Auth
    wb_user_id          String DEFAULT '',

    -- Indexes
    INDEX idx_trace_id trace_id TYPE bloom_filter GRANULARITY 1,
    INDEX idx_parent parent_span_id TYPE bloom_filter GRANULARITY 1,
    INDEX idx_op operation_name TYPE set(20) GRANULARITY 4,
    INDEX idx_provider provider_name TYPE set(20) GRANULARITY 4,
    INDEX idx_agent agent_name TYPE set(100) GRANULARITY 4,
    INDEX idx_model request_model TYPE set(100) GRANULARITY 4,
    INDEX idx_conv conversation_id TYPE set(100) GRANULARITY 4,
    INDEX idx_tool tool_name TYPE set(100) GRANULARITY 4
) ENGINE = ReplacingMergeTree(created_at)
PARTITION BY toYYYYMM(started_at)
ORDER BY (project_id, started_at, span_id)
SETTINGS min_bytes_for_wide_part=0, enable_block_number_column=1, enable_block_offset_column=1;
