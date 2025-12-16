/*
This migration creates the queue-based call annotation system tables.

The system consists of three main tables:
1. annotation_queues: Queue definitions with metadata and scorers
2. annotation_queue_items: Tracks which calls belong to each queue (membership)
3. annotator_queue_items_progress: Tracks per-annotator workflow state for each queue item

Key features:
- Lightweight UPDATE support via enable_block_number_column
- Multi-queue support (same call can be in multiple queues)
- Multi-annotator support with work claiming and expiration
- Display field selection for focused annotation
*/

-- ============================================================================
-- annotation_queues: Queue definitions and metadata
-- ============================================================================
CREATE TABLE annotation_queues (
    /*
    `id`: String (UUID format), unique identifier for the queue. This is the primary reference.
    */
    id String,

    /*
    `project_id`: The project identifier. This is an internal identifier that
    matches the project identifier in the W&B API.
    */
    project_id String,

    /*
    `name`: Human-readable name for the queue.
    */
    name String,

    /*
    `description`: Optional description of the queue's purpose.
    */
    description Nullable(String),

    /*
    `scorer_refs`: Array of scorer weave refs for annotation.
    Example: ['weave:///entity/project/scorer/error_severity:abc123']
    Native Array(String) type enables efficient access without JSON parsing.
    */
    scorer_refs Array(String),

    /*
    `created_at`: Timestamp when the queue was created.
    */
    created_at DateTime64(3) DEFAULT now64(3),

    /*
    `created_by`: W&B user ID who created the queue.
    */
    created_by String,

    /*
    `updated_at`: Timestamp when the queue was last modified.
    */
    updated_at DateTime64(3) DEFAULT now64(3),

    /*
    `deleted_at`: Soft delete timestamp. NULL means not deleted.
    */
    deleted_at Nullable(DateTime64(3))
) ENGINE = MergeTree()
ORDER BY (project_id, id)
SETTINGS
    enable_block_number_column = 1,
    enable_block_offset_column = 1;

-- ============================================================================
-- annotation_queue_items: Queue membership (which calls belong to each queue)
-- ============================================================================
CREATE TABLE annotation_queue_items (
    /*
    `id`: String (UUID format), unique identifier for this queue item. This is the primary reference.
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
    `call_id`: References calls_merged.id. The actual call being annotated.
    */
    call_id String,

    /*
    `call_started_at`: Cached from call for sorting/filtering without joins.
    Snapshot at add time.
    */
    call_started_at DateTime64(3),

    /*
    `call_ended_at`: Cached from call for sorting/filtering without joins.
    Snapshot at add time.
    */
    call_ended_at Nullable(DateTime64(3)),

    /*
    `call_op_name`: Cached from call for sorting/filtering without joins.
    Snapshot at add time.
    */
    call_op_name String,

    /*
    `call_trace_id`: Cached from call for sorting/filtering without joins.
    Snapshot at add time.
    */
    call_trace_id String,

    /*
    `display_fields`: JSON paths to show annotator, e.g., ['input.prompt', 'output.text'].
    Focuses annotator attention on relevant fields. Specified per batch when adding calls.
    */
    display_fields Array(String),

    /*
    `added_at`: Timestamp when this call was added to the queue.
    */
    added_at DateTime64(3) DEFAULT now64(3),

    /*
    `added_by`: W&B user ID who added this call to the queue.
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
    deleted_at Nullable(DateTime64(3))
) ENGINE = MergeTree()
ORDER BY (project_id, queue_id, id)
SETTINGS
    enable_block_number_column = 1,
    enable_block_offset_column = 1;

-- ============================================================================
-- Add queue_id to feedback table
-- ============================================================================
ALTER TABLE feedback
    /*
    `queue_id`: The queue ID this feedback was created from.
    References annotation_queues.id. NULL when feedback is created outside of queues.
    */
    ADD COLUMN queue_id Nullable(String) DEFAULT NULL;

-- ============================================================================
-- annotator_queue_items_progress: Per-annotator workflow state tracking
-- ============================================================================
CREATE TABLE annotator_queue_items_progress (
    /*
    `id`: String (UUID format), unique identifier for this progress record. This is the primary reference.
    */
    id String,

    /*
    `project_id`: The project identifier.
    */
    project_id String,

    /*
    `queue_item_id`: String (UUID format), references annotation_queue_items.id.
    */
    queue_item_id String,

    /*
    `queue_id`: String (UUID format), denormalized from queue_item for efficient querying without joins.
    */
    queue_id String,

    /*
    `call_id`: Denormalized from queue_item for efficient querying without joins.
    */
    call_id String,

    /*
    `annotator_id`: W&B user ID of the annotator.
    */
    annotator_id String,

    /*
    `annotation_state`: Workflow state of this item.
    - completed (0): Annotation finished
    - skipped (1): Annotator chose to skip
    */
    annotation_state Enum8(
        'completed' = 0,
        'skipped' = 1
    ) DEFAULT 'completed',

    /*
    `created_at`: Timestamp when the row was created.
    */
    created_at DateTime64(3) DEFAULT now64(3),

    /*
    `updated_at`: Timestamp when the row was last modified.
    */
    updated_at DateTime64(3) DEFAULT now64(3),

    /*
    `deleted_at`: Soft delete timestamp. NULL means not deleted.
    */
    deleted_at Nullable(DateTime64(3))
) ENGINE = MergeTree()
ORDER BY (project_id, queue_id, id)
SETTINGS
    enable_block_number_column = 1,
    enable_block_offset_column = 1;
