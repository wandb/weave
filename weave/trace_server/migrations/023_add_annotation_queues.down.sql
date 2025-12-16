/*
This migration removes the queue-based call annotation system tables.

IMPORTANT: This will permanently delete all queue data including:
- Queue definitions
- Queue item memberships
- Annotator progress records

Feedback records are stored separately and will not be deleted.
*/

-- Remove queue_id column from feedback table
ALTER TABLE feedback
    DROP COLUMN queue_id;

-- Drop tables in reverse dependency order
DROP TABLE IF EXISTS annotator_queue_items_progress;
DROP TABLE IF EXISTS annotation_queue_items;
DROP TABLE IF EXISTS annotation_queues;
