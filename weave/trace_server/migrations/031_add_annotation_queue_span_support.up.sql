/*
This migration extends the annotation queue system to support agent spans.

Changes:
1. Adds queue_type column to annotation_queues to distinguish call vs span queues
2. Creates annotation_queue_span_items table for span-based queue items

Existing call queues automatically get queue_type='call' via DEFAULT.
The annotation_queue_span_items table mirrors annotation_queue_items but with
span-specific cached metadata (agent_name, operation_name, etc.) instead of
call-specific fields (call_op_name, call_trace_id, etc.).

Progress tracking reuses the existing annotator_queue_items_progress table,
which references queue items by (queue_item_id, queue_id) regardless of
item type.
*/

-- ============================================================================
-- Add queue_type to annotation_queues
-- ============================================================================
ALTER TABLE annotation_queues
    ADD COLUMN queue_type Enum8('call' = 0, 'span' = 1) DEFAULT 'call';

-- ============================================================================
-- annotation_queue_span_items: Queue membership for agent spans
-- ============================================================================
CREATE TABLE annotation_queue_span_items (
    /*
    `id`: String (UUID format), unique identifier for this queue item.
    */
    id String,

    /*
    `project_id`: The project identifier.
    */
    project_id String,

    /*
    `queue_id`: String (UUID format), references annotation_queues.id.
    */
    queue_id String,

    /*
    `trace_id`: OTel trace ID. Together with span_id, identifies the specific span.
    */
    trace_id String,

    /*
    `span_id`: OTel span ID. Together with trace_id, identifies the specific span.
    */
    span_id String,

    /*
    Cached span metadata (snapshot at add time, avoids joins to spans table).
    */
    started_at DateTime64(6),
    ended_at DateTime64(6),
    operation_name String DEFAULT '',
    agent_name String DEFAULT '',
    provider_name String DEFAULT '',
    request_model String DEFAULT '',
    status_code String DEFAULT 'UNSET',
    input_tokens UInt64 DEFAULT 0,
    output_tokens UInt64 DEFAULT 0,
    conversation_id String DEFAULT '',

    /*
    `display_mode`: How the annotator UI should render this item.
    - chat_view (0): Render the full chat timeline for the trace
    - span_detail (1): Render the individual span's structured fields
    */
    display_mode Enum8('chat_view' = 0, 'span_detail' = 1) DEFAULT 'chat_view',

    /*
    `added_by`: W&B user ID who added this span to the queue.
    */
    added_by Nullable(String),

    /*
    `created_at`: Timestamp when the row was created.
    */
    created_at DateTime64(3) DEFAULT now64(3),

    /*
    `created_by`: W&B user ID who created this record.
    */
    created_by String,

    /*
    `updated_at`: Timestamp when the row was last modified.
    */
    updated_at DateTime64(3) DEFAULT now64(3),

    /*
    `deleted_at`: Soft delete timestamp. NULL means not deleted.
    */
    deleted_at Nullable(DateTime64(3)),

    -- Bloom filter indexes for fast lookups
    INDEX idx_trace_id trace_id TYPE bloom_filter GRANULARITY 1,
    INDEX idx_span_id span_id TYPE bloom_filter GRANULARITY 1
) ENGINE = MergeTree()
ORDER BY (project_id, queue_id, id)
SETTINGS
    enable_block_number_column = 1,
    enable_block_offset_column = 1;
