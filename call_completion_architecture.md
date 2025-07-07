# Call Completion Architecture Plan

## Current State

- **Data Flow**: Clients upload calls via `upsert_batch` → inserted into `call_parts` table
- **Call Parts Table**: Contains both call starts and call ends with same ID
- **Existing Queue**: Kafka topic `"weave.call_ended"` implemented in `kafka.py`
- **Producer**: `KafkaProducer.produce_call_end()` in `clickhouse_trace_server_batched.py`
- **Current Target**: `calls_merged` table (auto-aggregated from `call_parts` via materialized view)
- **Technology Stack**: Confluent Kafka, ClickHouse AggregatingMergeTree

## Proposed Architecture

### Option 1: Dual Queue Approach (Recommended)

```
┌─────────────────┐    ┌─────────────────┐
│   call_parts    │    │   call_parts    │
│   (call_start)  │    │   (call_end)    │
└─────────┬───────┘    └─────────┬───────┘
          │                      │
          ▼                      ▼
┌─────────────────┐    ┌─────────────────┐
│call_starts_queue│    │call_ends_queue  │
│    (new)        │    │   (existing)    │
└─────────┬───────┘    └─────────┬───────┘
          │                      │
          └──────────┬───────────┘
                     ▼
            ┌─────────────────┐
            │ Call Completion │
            │     Worker      │
            └─────────┬───────┘
                      ▼
            ┌─────────────────┐
            │ calls_complete  │
            │     Table       │
            └─────────────────┘
```

### Worker Logic Flow

1. **Poll call_ends_queue** continuously
2. **Query Database** for matching call_start (same ID)
3. **Decision Logic**:
   - ✅ Both exist → Insert into `calls_complete`
   - ❌ No call_start → Requeue with timestamp
   - ⏱️ Timeout (5min) → Insert error record

### Alternative Approaches

#### Option 2: Single Queue with Message Types

- Single queue handling both starts and ends
- Message payload includes type indicator
- **Pros**: Simpler infrastructure
- **Cons**: More complex worker logic

#### Option 3: Database-Driven Matching

- Use database triggers/views for matching
- Periodic batch processing
- **Pros**: Leverages database capabilities
- **Cons**: Less real-time, harder to debug

## Implementation Details

### Queue Infrastructure

- **Technology**: Confluent Kafka (`confluent_kafka` library)
- **Configuration**:
  - Bootstrap servers: `{WF_KAFKA_BROKER_HOST}:{WF_KAFKA_BROKER_PORT}`
  - Default: `localhost:9092`
  - Message timeout: 500ms
- **Topics**:
  - `CALL_STARTED_TOPIC = "weave.call_started"` (new)
  - `CALL_ENDED_TOPIC = "weave.call_ended"` (existing)
- **Producer**: Extend existing `KafkaProducer` class in `kafka.py`

### Worker Process

- **Pattern**: Follow existing `actions_worker/` structure
- **Deployment**: Separate pod with configurable scaling
- **Batch Processing**: Use existing patterns with `WF_SCORING_WORKER_BATCH_SIZE` (default: 100)
- **Timeout**: `WF_SCORING_WORKER_BATCH_TIMEOUT` (default: 5 seconds)
- **Error Handling**: Integration with existing exception tracking

### Database Schema

```sql
-- Target table: calls_merged (already exists)
-- Uses AggregatingMergeTree with SimpleAggregateFunction
-- Auto-populated from call_parts via materialized view

-- Potential enhancement for error tracking:
-- calls_merged already has 'exception' field for error states
```

### Key Implementation Files

- `weave/trace_server/kafka.py`: Add `produce_call_start()` method
- `weave/trace_server/clickhouse_trace_server_batched.py`: Add call_start publishing
- `weave/trace_server/environment.py`: Add worker configuration
- `weave/trace_server/completion_worker/`: New worker module (follow actions_worker pattern)

### Timeout Management

- **Approach**: In-memory tracking with Redis/database persistence
- **Timeout**: 5 minutes (configurable via environment)
- **Cleanup**: Periodic cleanup following existing worker patterns

## Implementation Plan

### Phase 1: Queue Infrastructure

1. **Add call_starts topic** to `kafka.py:77`
   ```python
   CALL_STARTED_TOPIC = "weave.call_started"
   ```
2. **Extend KafkaProducer** in `kafka.py:104` with `produce_call_start()` method
3. **Modify call_start()** in `clickhouse_trace_server_batched.py:463` to publish to queue
4. **Add environment variables** in `environment.py` for worker configuration

### Phase 2: Worker Implementation

1. **Create completion_worker directory** following `actions_worker/` pattern
2. **Implement CallCompletionWorker** class with:
   - Kafka consumer for call_ends queue
   - Database lookup for matching call_starts
   - Timeout tracking with configurable 5-minute window
   - Error handling for orphaned calls
3. **Add worker configuration** and deployment scripts

### Phase 3: Integration & Testing

1. **Update deployment** configurations for new worker pod
2. **End-to-end testing** with call start/end scenarios
3. **Monitor queue metrics** and processing latency
4. **Performance tuning** for batch sizes and timeouts

## Considerations

### Performance

- **Queue Throughput**: Estimate based on current call volume
- **Database Queries**: Index on call ID for fast lookups
- **Worker Scaling**: Auto-scaling based on queue depth

### Reliability

- **Message Ordering**: Use call ID as partition key
- **Duplicate Handling**: Idempotent operations
- **Failure Recovery**: Graceful degradation

### Monitoring

- Queue depth and lag
- Match success rate
- Processing latency
- Error rates

## Migration Plan

### Option 1: Dual Path Migration (Recommended)

**Phase 1: Deployment (Week 1)**

1. **Deploy new `calls_complete` table** alongside existing `calls_merged`
2. **Deploy completion worker** with queue processing
3. **Enable dual-write** - both old and new paths active
4. **Set migration cutoff date** - `MIGRATION_CUTOFF_DATE` environment variable

**Phase 2: Soaking Period (Weeks 2-5)**

1. **Query routing logic**:
   ```python
   if query.date_filter and query.start_date >= MIGRATION_CUTOFF_DATE:
       # Serve from calls_complete (new path)
       return query_calls_complete(query)
   else:
       # Serve from calls_merged (old path)
       return query_calls_merged(query)
   ```
2. **Monitor both paths** for data consistency and performance
3. **Validate completeness** - compare call counts and data integrity

**Phase 3: Backfill (Weeks 6-12)**

1. **Batch backfill process**:
   - Start from `MIGRATION_CUTOFF_DATE`
   - Process in 1-day batches moving backwards
   - Rate-limited to avoid database overload
   - Checkpoint progress for resumability
2. **Backfill worker**:
   ```python
   def backfill_calls_complete(start_date, end_date):
       # Query calls_merged for complete calls in date range
       # Insert into calls_complete
       # Update backfill_progress table
   ```

**Phase 4: Cutover (Week 13)**

1. **Switch all queries** to `calls_complete` table
2. **Monitor performance** and rollback capability
3. **Deprecate old path** after 2-week observation period

### Option 2: Feature Flag Migration

**Benefits**: Granular control, easy rollback
**Implementation**:

- Environment variable: `ENABLE_CALL_COMPLETION_WORKER`
- Per-project feature flags for query routing
- Gradual rollout by customer/project

### Option 3: Staged Customer Migration

**Benefits**: Risk isolation, customer-specific validation
**Implementation**:

- Migrate high-volume customers first
- Customer whitelist for new path
- Fallback to old path for non-whitelisted customers

### Option 4: Big Bang Migration

**Benefits**: Simplest implementation
**Risks**: High risk, difficult rollback
**Not Recommended**: For production system with existing data

## Migration Implementation Details

### Database Schema Changes

```sql
-- New calls_complete table
CREATE TABLE calls_complete (
    id String,
    project_id String,
    -- ... (mirror calls_merged schema)
    completion_source Enum('worker', 'backfill', 'realtime'),
    created_at DateTime64(3) DEFAULT now()
) ENGINE = MergeTree()
ORDER BY (project_id, id);

-- Migration tracking
CREATE TABLE backfill_progress (
    batch_date Date,
    status Enum('pending', 'processing', 'completed', 'failed'),
    processed_count UInt64,
    error_count UInt64,
    updated_at DateTime64(3) DEFAULT now()
) ENGINE = MergeTree()
ORDER BY batch_date;
```

### Query Router Implementation

```python
# In clickhouse_trace_server_batched.py
def query_calls_with_migration_support(query):
    if should_use_new_path(query):
        return self.ch_client.query_calls_complete(query)
    else:
        return self.ch_client.query_calls_merged(query)

def should_use_new_path(query):
    # Check feature flags, date filters, customer whitelist
    if not wf_env.enable_call_completion_worker():
        return False

    if query.date_filter and query.start_date >= MIGRATION_CUTOFF_DATE:
        return is_backfill_complete(query.start_date)

    return False
```

### Monitoring & Validation

- **Data Consistency**: Compare call counts between old/new paths
- **Performance Metrics**: Query latency, worker processing time
- **Error Tracking**: Failed completions, timeout rates
- **Backfill Progress**: Batch completion rates, error counts

### Rollback Strategy

1. **Immediate**: Disable feature flag to route all traffic to old path
2. **Gradual**: Reduce traffic percentage to new path
3. **Emergency**: Hard-coded fallback in query router

## Questions for Discussion

1. Should we use separate workers for different queue types?
2. What's the expected call volume and required latency?
3. How should we handle duplicate calls?
4. What monitoring/alerting is needed?
5. **Migration Questions**:
   - What's the acceptable backfill processing time?
   - How should we handle data inconsistencies during migration?
   - What rollback criteria should trigger automatic failover?
