package main

import (
	"encoding/json"
	"sync"
)

// QueueEntry represents a single entry in the queue
type QueueEntry struct {
	ID        uint64          `json:"id"`
	Type      string          `json:"type"` // "start" or "end"
	Payload   json.RawMessage `json:"payload"`
	Timestamp int64           `json:"timestamp"`
}

// Queue is a simple in-memory queue
type Queue struct {
	mu       sync.Mutex
	entries  []QueueEntry
	nextID   uint64
	maxSize  int
	dropped  uint64
}

// NewQueue creates a new in-memory queue
func NewQueue(maxSize int) *Queue {
	if maxSize <= 0 {
		maxSize = 100000 // Default 100k items
	}
	return &Queue{
		entries: make([]QueueEntry, 0, 1000),
		nextID:  1,
		maxSize: maxSize,
	}
}

// Enqueue adds entries to the queue and returns their IDs
func (q *Queue) Enqueue(entries []QueueEntry) []uint64 {
	q.mu.Lock()
	defer q.mu.Unlock()

	ids := make([]uint64, 0, len(entries))

	for _, entry := range entries {
		// Check capacity
		if len(q.entries) >= q.maxSize {
			q.dropped++
			continue
		}

		entry.ID = q.nextID
		q.nextID++
		q.entries = append(q.entries, entry)
		ids = append(ids, entry.ID)
	}

	return ids
}

// Dequeue removes and returns up to n entries from the front
func (q *Queue) Dequeue(n int) []QueueEntry {
	q.mu.Lock()
	defer q.mu.Unlock()

	if len(q.entries) == 0 {
		return nil
	}

	if n > len(q.entries) {
		n = len(q.entries)
	}

	result := make([]QueueEntry, n)
	copy(result, q.entries[:n])
	q.entries = q.entries[n:]

	return result
}

// Peek returns up to n entries without removing them.
// If n <= 0, returns all entries.
func (q *Queue) Peek(n int) []QueueEntry {
	q.mu.Lock()
	defer q.mu.Unlock()

	if len(q.entries) == 0 {
		return nil
	}

	if n <= 0 || n > len(q.entries) {
		n = len(q.entries)
	}

	result := make([]QueueEntry, n)
	copy(result, q.entries[:n])
	return result
}

// Len returns the current queue length
func (q *Queue) Len() int {
	q.mu.Lock()
	defer q.mu.Unlock()
	return len(q.entries)
}

// DroppedCount returns the number of dropped entries
func (q *Queue) DroppedCount() uint64 {
	q.mu.Lock()
	defer q.mu.Unlock()
	return q.dropped
}

// Requeue adds entries back to the front of the queue (for retries)
func (q *Queue) Requeue(entries []QueueEntry) {
	q.mu.Lock()
	defer q.mu.Unlock()

	// Prepend entries
	q.entries = append(entries, q.entries...)
}
