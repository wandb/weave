package main

import (
	"context"
	"encoding/json"
	"log"
	"sync"
	"time"
)

// BatchConfig configures the batcher behavior
type BatchConfig struct {
	MaxBatchSize    int           // Maximum number of items per batch
	MaxBatchBytes   int           // Maximum bytes per batch (for HTTP limit)
	FlushInterval   time.Duration // How often to flush batches
	MaxRetries      int           // Maximum retries for failed batches
	RetryBackoff    time.Duration // Initial backoff between retries
	MaxRetryBackoff time.Duration // Maximum backoff between retries
}

// DefaultBatchConfig returns sensible defaults
func DefaultBatchConfig() BatchConfig {
	return BatchConfig{
		MaxBatchSize:    1000,             // Higher default since byte limit is the real constraint
		MaxBatchBytes:   31 * 1024 * 1024, // 31 MiB (server limit is 32)
		FlushInterval:   time.Second,
		MaxRetries:      3,
		RetryBackoff:    100 * time.Millisecond,
		MaxRetryBackoff: 5 * time.Second,
	}
}

// Batcher assembles queue entries into batches and sends them
type Batcher struct {
	config BatchConfig
	queue  *Queue
	sender *HTTPSender

	// Control
	ctx    context.Context
	cancel context.CancelFunc
	wg     sync.WaitGroup

	// Stats
	mu          sync.RWMutex
	sentCount   uint64
	failedCount uint64

	// In-flight tracking
	inFlight   int
	inFlightMu sync.Mutex
	idleCond   *sync.Cond
}

// NewBatcher creates a new batcher
func NewBatcher(config BatchConfig, queue *Queue, sender *HTTPSender) *Batcher {
	ctx, cancel := context.WithCancel(context.Background())

	b := &Batcher{
		config: config,
		queue:  queue,
		sender: sender,
		ctx:    ctx,
		cancel: cancel,
	}
	b.idleCond = sync.NewCond(&b.inFlightMu)
	return b
}

// Start begins the batching goroutine
func (b *Batcher) Start() {
	b.wg.Add(1)
	go b.processLoop()
}

// Stop gracefully stops the batcher, flushing remaining items
func (b *Batcher) Stop() {
	b.cancel()
	b.wg.Wait()
}

// Stats returns current statistics
func (b *Batcher) Stats() (sent, failed uint64) {
	b.mu.RLock()
	defer b.mu.RUnlock()
	return b.sentCount, b.failedCount
}

// InFlight returns the number of batches currently being sent
func (b *Batcher) InFlight() int {
	b.inFlightMu.Lock()
	defer b.inFlightMu.Unlock()
	return b.inFlight
}

// WaitIdle blocks until queue is empty and no batches are in flight
func (b *Batcher) WaitIdle() {
	b.inFlightMu.Lock()
	defer b.inFlightMu.Unlock()
	for b.inFlight > 0 || b.queue.Len() > 0 {
		b.idleCond.Wait()
	}
}

func (b *Batcher) processLoop() {
	defer b.wg.Done()

	ticker := time.NewTicker(b.config.FlushInterval)
	defer ticker.Stop()

	for {
		select {
		case <-b.ctx.Done():
			// Final flush before exit
			b.flushAll()
			return
		case <-ticker.C:
			b.flushAll()
		}
	}
}

// FlushAll flushes all pending items (exported for manual flush)
func (b *Batcher) FlushAll() {
	b.flushAll()
}

func (b *Batcher) flushAll() {
	for {
		flushed := b.flushBatch()
		if !flushed {
			return // No more items to flush
		}
	}
}

func (b *Batcher) flushBatch() bool {
	// Peek at entries (don't dequeue yet in case send fails)
	entries := b.queue.Peek(b.config.MaxBatchSize)
	if len(entries) == 0 {
		// Signal that we might be idle
		b.inFlightMu.Lock()
		if b.inFlight == 0 && b.queue.Len() == 0 {
			b.idleCond.Broadcast()
		}
		b.inFlightMu.Unlock()
		return false
	}

	// Build batch, respecting byte limits
	batch, count := b.buildBatch(entries)
	if len(batch.Items) == 0 {
		return false
	}

	// Mark as in-flight
	b.inFlightMu.Lock()
	b.inFlight++
	b.inFlightMu.Unlock()

	if Verbose {
		var totalBytes int
		for _, item := range batch.Items {
			totalBytes += len(item.Payload)
		}
		log.Printf("[BATCH] sending %d items (%d bytes)", len(batch.Items), totalBytes)
	}

	// Send with retries
	if err := b.sendWithRetry(batch); err != nil {
		log.Printf("[BATCH] FAILED after retries: %v", err)
		b.mu.Lock()
		b.failedCount += uint64(len(batch.Items))
		b.mu.Unlock()

		// Dequeue failed items so we don't retry forever
		b.queue.Dequeue(count)

		// Mark as no longer in-flight
		b.inFlightMu.Lock()
		b.inFlight--
		if b.inFlight == 0 && b.queue.Len() == 0 {
			b.idleCond.Broadcast()
		}
		b.inFlightMu.Unlock()
		return true
	}

	if Verbose {
		log.Printf("[BATCH] SUCCESS sent %d items", len(batch.Items))
	}

	// Success - dequeue the sent items
	b.queue.Dequeue(count)

	// Update stats
	b.mu.Lock()
	b.sentCount += uint64(len(batch.Items))
	b.mu.Unlock()

	// Mark as no longer in-flight and signal if idle
	b.inFlightMu.Lock()
	b.inFlight--
	if b.inFlight == 0 && b.queue.Len() == 0 {
		b.idleCond.Broadcast()
	}
	b.inFlightMu.Unlock()

	return true
}

// BatchItem wraps a queue entry for sending
type BatchItem struct {
	Type    string          // "start" or "end"
	Payload json.RawMessage
}

// Batch is a collection of items to send
type Batch struct {
	Items []BatchItem
}

func (b *Batcher) buildBatch(entries []QueueEntry) (Batch, int) {
	var batch Batch
	var totalBytes int
	var count int

	for _, entry := range entries {
		itemBytes := len(entry.Payload)

		// Check if adding this item would exceed byte limit
		if totalBytes+itemBytes > b.config.MaxBatchBytes && len(batch.Items) > 0 {
			break
		}

		batch.Items = append(batch.Items, BatchItem{
			Type:    entry.Type,
			Payload: entry.Payload,
		})
		totalBytes += itemBytes
		count++

		// Check item count limit
		if len(batch.Items) >= b.config.MaxBatchSize {
			break
		}
	}

	return batch, count
}

func (b *Batcher) sendWithRetry(batch Batch) error {
	var lastErr error
	backoff := b.config.RetryBackoff

	for attempt := 0; attempt <= b.config.MaxRetries; attempt++ {
		if attempt > 0 {
			select {
			case <-b.ctx.Done():
				return b.ctx.Err()
			case <-time.After(backoff):
			}
			backoff *= 2
			if backoff > b.config.MaxRetryBackoff {
				backoff = b.config.MaxRetryBackoff
			}
		}

		err := b.sender.SendBatch(b.ctx, batch)
		if err == nil {
			return nil
		}

		lastErr = err
		log.Printf("Batch send attempt %d failed: %v", attempt+1, err)

		// Don't retry non-retryable errors
		if !isRetryable(err) {
			return err
		}
	}

	return lastErr
}

func isRetryable(err error) bool {
	// Check for HTTP errors
	if httpErr, ok := err.(*HTTPError); ok {
		return httpErr.IsRetryable()
	}

	// For context errors, don't retry
	if err == context.Canceled || err == context.DeadlineExceeded {
		return false
	}

	// Retry other errors (network issues, etc.)
	return true
}
