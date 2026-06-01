DROP TABLE IF EXISTS annotation_queue_span_items;

ALTER TABLE annotation_queues DROP COLUMN IF EXISTS queue_type;
