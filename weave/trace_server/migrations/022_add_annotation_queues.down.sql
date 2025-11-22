/*
This migration removes the queue-based call annotation system tables.

IMPORTANT: This will permanently delete all queue data including:
- Queue definitions
- Queue item memberships
- Annotator progress records

Feedback records are stored separately and will not be deleted.
*/

-- Drop tables in reverse dependency order
DROP TABLE IF EXISTS annotator_queue_items_progress;
DROP TABLE IF EXISTS annotation_queue_items;
DROP TABLE IF EXISTS annotation_queues;
