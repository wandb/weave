# Dynamic Trace Aggregation Design Document

## Problem Statement

Weave traces are deeply nested with arbitrary depth and branching. Each node (call) in the trace tree can have metrics in the form of:
- **Inputs/Outputs**: Stored as JSON in `inputs_dump` and `output_dump`
- **Feedback Scores**: Stored in a separate `feedback` table, linked via `weave_ref`

**Goal**: Dynamically aggregate metrics from child nodes up to parent nodes. For example, if nodes D and E have a "quality" score of 1 and 2 respectively, their parent B should show an aggregated "quality" score (e.g., mean = 1.5).

```
A
├── B (aggregated quality = 1.5)
│   ├── D (quality = 1)
│   └── E (quality = 2)
└── C
    └── F
```

## Current Data Model

### Call Storage (ClickHouse)

The primary table for queries is `calls_complete`:

```sql
CREATE TABLE calls_complete (
    project_id String,
    id String,                              -- Call UUID
    trace_id String,                        -- Groups all calls in a trace
    parent_id Nullable(String),             -- Direct parent (enables tree traversal)
    op_name String,
    started_at DateTime64(6),
    ended_at Nullable(DateTime64(6)),
    inputs_dump String,                     -- JSON inputs
    output_dump String,                     -- JSON output
    summary_dump String,                    -- JSON summary with nested feedback
    -- ... other fields
)
ENGINE = MergeTree()
ORDER BY (project_id, started_at, id)
```

Key fields for hierarchy:
- `trace_id`: Groups all calls belonging to the same trace
- `parent_id`: Points to the direct parent call (NULL for root)

### Feedback Storage

Feedback is stored separately and linked to calls via URI reference:

```sql
CREATE TABLE feedback (
    project_id String,
    weave_ref String,                       -- e.g., "weave:///entity/project/call/call_id"
    feedback_type String,                   -- e.g., "quality", "wandb.runnable.my_scorer"
    payload_dump String,                    -- JSON: {"value": 1.5} or {"output": {...}}
    -- ... other fields
)
```

Payload structures:
- Simple score: `{"value": 4}` or `{"value": 0.5}`
- Scorer output: `{"output": {"score": 0.85, "match": true}}`
- Annotation: `{"value": <any>}` validated against schema

## ClickHouse Capabilities

### Recursive CTEs (Available since v24.4)

ClickHouse supports recursive CTEs with `WITH RECURSIVE`:

```sql
WITH RECURSIVE tree AS (
    -- Base case: start from specific node
    SELECT id, parent_id, 0 AS depth
    FROM calls_complete
    WHERE id = 'target_call_id'

    UNION ALL

    -- Recursive case: find children
    SELECT c.id, c.parent_id, t.depth + 1
    FROM calls_complete c
    JOIN tree t ON c.parent_id = t.id
)
SELECT * FROM tree;
```

**Current version in CI**: `25.11.2.24` (fully supports recursive CTEs)

**Required Setting**: Recursive CTEs require the new query analyzer:
```sql
SET enable_analyzer = 1;  -- Required for v24.8+
-- Or: SET allow_experimental_analyzer = 1;  -- For v24.3-24.7
```

**Limitations**:
- Default max depth: 1000 (configurable via `max_recursive_cte_evaluation_depth`)
- Each row visited once - bottom-up aggregation requires **two CTEs**
- Cannot be used in materialized views directly
- Memory-intensive for wide or deep trees
- **No automatic cycle detection** - must track visited nodes manually to avoid infinite loops
- **Data type overflow bug**: Using small integer types (Int8, UInt8) can cause infinite loops due to overflow

### Materialized Views - Critical Limitations

**ClickHouse materialized views are INSERT triggers, not traditional views.**

This is fundamentally different from PostgreSQL or other databases:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ CRITICAL: What ClickHouse Materialized Views CAN and CANNOT Do              │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│ ✓ CAN:  Trigger on INSERT to the source table (left-most table in query)  │
│ ✓ CAN:  Transform/aggregate data and insert into a target table           │
│ ✓ CAN:  JOIN with other tables at insert time (snapshot of joined data)   │
│                                                                             │
│ ✗ CANNOT: Trigger on UPDATE or DELETE                                      │
│ ✗ CANNOT: Trigger when joined tables change                                │
│ ✗ CANNOT: Do "cascade updates" to other tables automatically              │
│ ✗ CANNOT: Re-process historical data (only sees new inserts)              │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

**Implication for our use case**: When feedback is inserted into the `feedback` table,
a materialized view CANNOT automatically update aggregate rows in a different table
for all ancestor calls. The cascade logic must be handled at the **application level**.

### Existing Recursive Query Pattern

The SQLite trace server already uses recursive CTEs for cascading deletes:

```python
# weave/trace_server/sqlite_trace_server.py:742-757
WITH RECURSIVE Descendants AS (
    SELECT id FROM calls
    WHERE parent_id IN (SELECT id FROM calls WHERE id IN (?))

    UNION ALL

    SELECT c.id FROM calls c
    JOIN Descendants d ON c.parent_id = d.id
)
SELECT id FROM Descendants;
```

## Proposed Approaches

### Approach 1: Query-Time Recursive CTE (Recommended for Initial Implementation)

**Strategy**: Use recursive CTEs at query time to traverse the tree and aggregate scores.

**Two-Phase Aggregation** (required for bottom-up):

```sql
-- Phase 1: Collect all descendants with their scores
WITH RECURSIVE
descendants AS (
    -- Start from target node
    SELECT
        c.id,
        c.parent_id,
        f.payload_dump,
        [c.id] AS path,
        0 AS depth
    FROM calls_complete c
    LEFT JOIN feedback f ON f.weave_ref = concat('weave:///', c.project_id, '/call/', c.id)
        AND f.feedback_type = 'quality'
    WHERE c.id = 'target_call_id' AND c.project_id = 'my_project'

    UNION ALL

    -- Find children
    SELECT
        c.id,
        c.parent_id,
        f.payload_dump,
        arrayConcat(d.path, [c.id]) AS path,
        d.depth + 1
    FROM calls_complete c
    JOIN descendants d ON c.parent_id = d.id
    LEFT JOIN feedback f ON f.weave_ref = concat('weave:///', c.project_id, '/call/', c.id)
        AND f.feedback_type = 'quality'
    WHERE c.project_id = 'my_project' AND NOT has(d.path, c.id)
),
-- Phase 2: Aggregate from leaves up
scores AS (
    SELECT
        id,
        parent_id,
        depth,
        JSONExtractFloat(payload_dump, 'value') AS direct_score
    FROM descendants
)
SELECT
    id,
    direct_score,
    avg(direct_score) OVER (
        PARTITION BY parent_id
    ) AS sibling_avg
FROM scores
ORDER BY depth DESC;
```

**Pros**:
- Fully dynamic - works with any tree structure
- No schema changes required
- Leverages existing indexes

**Cons**:
- Performance degrades with tree depth/width
- High memory usage for large traces
- Must be computed on every query

### Approach 2: Materialized Path Pattern

**Strategy**: Store the full path from root to each node, enabling efficient ancestor/descendant queries.

#### The Analogy: Street Addresses

Think of how postal addresses work. Instead of describing your location as "the house whose parent is Elm Street, whose parent is Downtown, whose parent is Springfield", you just say:

```
123 Elm Street, Downtown, Springfield, USA
```

This is a **materialized path** - the full ancestry is embedded in the address itself. Anyone can instantly tell:
- You're in Springfield (contains "Springfield")
- You're in Downtown (contains "Downtown")
- You're on Elm Street (contains "Elm Street")

No need to recursively look up "what neighborhood is Elm Street in?" then "what city is Downtown in?" etc.

#### How It Works

```
Current Schema (parent_id only):          With Materialized Path:
┌─────────────────────────────┐           ┌────────────────────────────────────────────┐
│ id │ parent_id │ score     │           │ id │ parent_id │ path              │ score │
├────┼───────────┼───────────┤           ├────┼───────────┼───────────────────┼───────┤
│ A  │ NULL      │ -         │           │ A  │ NULL      │ [A]               │ -     │
│ B  │ A         │ -         │           │ B  │ A         │ [A, B]            │ -     │
│ C  │ A         │ -         │           │ C  │ A         │ [A, C]            │ -     │
│ D  │ B         │ 1         │           │ D  │ B         │ [A, B, D]         │ 1     │
│ E  │ B         │ 2         │           │ E  │ B         │ [A, B, E]         │ 2     │
│ F  │ C         │ 3         │           │ F  │ C         │ [A, C, F]         │ 3     │
└─────────────────────────────┘           └────────────────────────────────────────────┘

Tree structure:
       A
      / \
     B   C
    / \   \
   D   E   F
  (1) (2) (3)
```

#### Query Comparison

**Without materialized path** (recursive):
```sql
-- "Find all descendants of B and aggregate their scores"
-- Must recursively traverse: B -> D, B -> E
WITH RECURSIVE descendants AS (
    SELECT id FROM calls WHERE id = 'B'
    UNION ALL
    SELECT c.id FROM calls c
    JOIN descendants d ON c.parent_id = d.id
)
SELECT avg(score) FROM descendants JOIN feedback...
-- Multiple iterations, grows with tree depth
```

**With materialized path** (single scan):
```sql
-- "Find all descendants of B and aggregate their scores"
-- Just check if 'B' is in the path array
SELECT avg(score)
FROM calls_complete
WHERE has(path, 'B')  -- O(1) array membership check
-- Single table scan, no recursion!
```

#### Visual: How Queries Work

```
Query: "Get aggregate score for B's subtree"

Without Path (must traverse):        With Path (direct lookup):

    Start at B                           SELECT WHERE has(path, 'B')
        │                                        │
        ▼                                        ▼
   ┌─────────┐                          ┌─────────────────────┐
   │ Find    │                          │ Scan paths:         │
   │ B's     │──► D (score=1)           │  [A,B,D] ✓ has B   │──► D
   │ children│──► E (score=2)           │  [A,B,E] ✓ has B   │──► E
   └─────────┘                          │  [A,C,F] ✗ no B    │
        │                               └─────────────────────┘
   Must recurse                              Single pass!
   for deeper trees
```

#### Bonus: Level-Aware Aggregation

The path also tells you the **depth relationship**:

```sql
-- "What's the average score of B's DIRECT children only?"
SELECT avg(score)
FROM calls_complete
WHERE path[length(path) - 1] = 'B'  -- Parent is B (second-to-last in path)

-- "What's the average score at each level below B?"
SELECT
    length(path) - indexOf(path, 'B') AS depth_from_B,
    avg(score)
FROM calls_complete
WHERE has(path, 'B')
GROUP BY depth_from_B
```

#### Schema Addition
```sql
ALTER TABLE calls_complete ADD COLUMN path Array(String);
-- path = ['root_id', 'parent_id', ..., 'current_id']
```

**Pros**:
- O(1) ancestor check via `has(path, id)`
- Efficient subtree queries - no recursion needed
- Can leverage Array bloom filter indexes
- Depth information is implicit in array position

**Cons**:
- Requires schema migration
- Path must be populated at insert time (add ~50 bytes per call for typical depths)
- Path updates needed if tree restructured (rare for traces - trees are typically immutable)

### Approach 3: Pre-computed Aggregations with Materialized Views

**Strategy**: Pre-compute aggregations when feedback is inserted.

#### The Analogy: Running Totals in Accounting

Imagine you're managing expenses for a company with departments:

```
Company (CEO)
├── Engineering (VP Eng)
│   ├── Backend Team
│   └── Frontend Team
└── Sales (VP Sales)
    └── Enterprise Team
```

**Without pre-computation** (like a recursive CTE):
Every time the CEO asks "what's our total spend?", an accountant must:
1. Call Backend Team: "What did you spend?" → $10k
2. Call Frontend Team: "What did you spend?" → $15k
3. Add those up for Engineering: $25k
4. Call Enterprise Team: "What did you spend?" → $20k
5. That's Sales: $20k
6. Total: $45k

This is slow and gets worse with more teams.

**With pre-computation**:
Each team maintains a "subtree total" that includes themselves + all sub-teams.
When Backend spends $1k, they:
1. Update their own total: $10k → $11k
2. Notify Engineering: "Add $1k to your subtree"
3. Engineering notifies CEO: "Add $1k to your subtree"

Now when the CEO asks "what's our total?", the answer is instant - it's already computed!

#### How It Works

```
Step 1: Initial State (no scores yet)

       A (subtree_sum=0, subtree_count=0)
      / \
     B   C
    / \   \
   D   E   F

Step 2: Score added to D (quality=1)

  Feedback inserted: D gets score 1
        │
        ▼
  ┌─────────────────────────────────────────┐
  │ CASCADE UPDATE (bottom-up):              │
  │                                          │
  │  1. Update D: direct_sum=1, direct_count=1│
  │  2. Find D's parent (B), update B:       │
  │     subtree_sum += 1, subtree_count += 1 │
  │  3. Find B's parent (A), update A:       │
  │     subtree_sum += 1, subtree_count += 1 │
  └─────────────────────────────────────────┘

  Result:
       A (subtree: sum=1, count=1, avg=1.0)
      / \
     B   C
   (subtree: sum=1, count=1)
    / \   \
   D   E   F
 (direct: 1)

Step 3: Score added to E (quality=2)

  Same cascade: E→B→A

  Result:
       A (subtree: sum=3, count=2, avg=1.5)
      / \
     B   C
   (subtree: sum=3, count=2, avg=1.5)
    / \   \
   D   E   F
 (1)  (2)

Step 4: Query "What's the average quality under B?"

  SELECT subtree_sum / subtree_count
  FROM call_score_aggregates
  WHERE call_id = 'B'

  Answer: 3/2 = 1.5  ← Instant! No tree traversal needed.
```

#### The Data Model

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        call_score_aggregates                            │
├──────────┬────────────────┬──────────────┬──────────────┬──────────────┤
│ call_id  │ feedback_type  │ direct_sum   │ direct_count │ subtree_sum  │ ...
├──────────┼────────────────┼──────────────┼──────────────┼──────────────┤
│ A        │ quality        │ 0            │ 0            │ 3            │
│ B        │ quality        │ 0            │ 0            │ 3            │
│ C        │ quality        │ 0            │ 0            │ 0            │
│ D        │ quality        │ 1            │ 1            │ 1            │
│ E        │ quality        │ 2            │ 1            │ 2            │
│ F        │ quality        │ 0            │ 0            │ 0            │
└──────────┴────────────────┴──────────────┴──────────────┴──────────────┘

direct_* = scores directly on this call
subtree_* = scores on this call + all descendants
```

#### Implementation Options

**IMPORTANT**: Due to ClickHouse materialized view limitations (see above), the cascade
logic CANNOT be implemented purely in ClickHouse. It must be done at the **application level**.

**Option A: Synchronous Cascade in Application Code (simpler, slower writes)**

```
┌──────────────┐                    ┌─────────────────────────────────────┐
│   Client     │                    │         Application Server          │
└──────┬───────┘                    │                                     │
       │                            │  1. Look up call's path: [A, B, D]  │
       │ add_feedback(call_id=D)    │  2. INSERT feedback for D           │
       │───────────────────────────►│  3. For each ancestor in path:      │
       │                            │     INSERT INTO aggregates table    │
       │                            │                                     │
       │◄───────────────────────────│  4. Return success                  │
       │                            └─────────────────────────────────────┘

Write latency: O(tree_depth) - application must insert multiple rows
```

**Option B: Async Processing with Queue (complex, fast writes)**

```
┌──────────────┐                    ┌─────────────────────────────────────┐
│   Client     │                    │         Application Server          │
└──────┬───────┘                    │                                     │
       │                            │  1. INSERT feedback for D           │
       │ add_feedback(call_id=D)    │  2. Enqueue: {call_id: D, score: 1} │
       │───────────────────────────►│  3. Return immediately              │
       │                            │                                     │
       │◄───────────────────────────│                                     │
       │  (fast response)           └─────────────────────────────────────┘
                                                    │
                                                    │ Queue message
                                                    ▼
                                    ┌─────────────────────────────────────┐
                                    │         Background Worker           │
                                    │                                     │
                                    │  1. Read message from queue         │
                                    │  2. Look up call's path: [A, B, D]  │
                                    │  3. For each ancestor:              │
                                    │     INSERT INTO aggregates table    │
                                    │                                     │
                                    └─────────────────────────────────────┘

Write latency: O(1) for client, aggregates eventually consistent
```

**Why not a ClickHouse Materialized View?**
- MV only triggers on INSERT to the source table
- When feedback is inserted, we need to update MULTIPLE rows in aggregates (one per ancestor)
- MV cannot "fan out" one insert to multiple target rows in different tables
- The ancestor lookup requires either recursive CTE or path array - neither works in MV context

#### ClickHouse-Specific Implementation

```sql
-- Aggregates table using AggregatingMergeTree
CREATE TABLE call_score_aggregates (
    project_id String,
    call_id String,
    feedback_type String,

    -- Direct scores on this call
    direct_count AggregateFunction(count, UInt64),
    direct_sum AggregateFunction(sum, Float64),

    -- Subtree scores (includes descendants)
    subtree_count AggregateFunction(count, UInt64),
    subtree_sum AggregateFunction(sum, Float64),

    updated_at DateTime64(3)
)
ENGINE = AggregatingMergeTree()
ORDER BY (project_id, call_id, feedback_type);

-- Query the aggregates (uses -Merge suffix to finalize)
SELECT
    call_id,
    sumMerge(direct_sum) / countMerge(direct_count) AS direct_avg,
    sumMerge(subtree_sum) / countMerge(subtree_count) AS subtree_avg
FROM call_score_aggregates
WHERE call_id = 'B' AND feedback_type = 'quality'
GROUP BY call_id;
```

#### The Cascade Challenge

The tricky part is the cascade update. When feedback is added to node D, we need to update D, B, and A. This requires knowing the ancestors, which brings us back to... needing either:

1. **Recursive CTE** at write time (to find ancestors)
2. **Materialized path** (to know ancestors directly)

```
Recommended: Combine with Materialized Path

┌─────────────────────────────────────────────────────────────────┐
│ calls_complete table                                            │
│ ┌────────┬─────────────────┬───────┐                            │
│ │ id     │ path            │ ...   │                            │
│ ├────────┼─────────────────┼───────┤                            │
│ │ D      │ [A, B, D]       │ ...   │  ← Path tells us ancestors │
│ └────────┴─────────────────┴───────┘                            │
└─────────────────────────────────────────────────────────────────┘

When feedback added to D:
  1. Look up D's path: [A, B, D]
  2. For each ancestor in path:
       INSERT INTO call_score_aggregates
       (call_id, subtree_sum, subtree_count)
       VALUES
       ('A', sumState(score), countState()),
       ('B', sumState(score), countState()),
       ('D', sumState(score), countState())  -- Also update direct_* for D
```

**Pros**:
- Query-time O(1) lookups - just read the pre-computed value
- No recursive queries needed at read time
- Scales to massive datasets

**Cons**:
- Complex cascade logic on write
- Write amplification: 1 feedback insert → N ancestor updates
- Eventually consistent (if using async)
- Requires materialized path or recursive lookup to find ancestors
- Storage overhead for aggregate table

### Approach 4: Hybrid - Cached Recursive Results

**Strategy**: Compute aggregations on-demand but cache results with TTL.

**Implementation**:
1. First query: Execute recursive CTE, cache result
2. Subsequent queries: Return cached result
3. Cache invalidation: On feedback insert/update

This could use ClickHouse's query result cache or an external cache (Redis).

**Pros**:
- Best of both worlds: dynamic + performant
- Automatic cache warming via usage patterns

**Cons**:
- Cache invalidation complexity
- Stale data during cache miss window

## Recommended Implementation Path

### Phase 1: Query-Time Recursive CTE (MVP)

Start with recursive CTEs for flexibility and validation:

1. **Create aggregation function** in `calls_query_builder/`:
   ```python
   def build_subtree_score_aggregation_query(
       project_id: str,
       call_id: str,
       feedback_type: str,
       aggregation: Literal["mean", "sum", "min", "max", "count"]
   ) -> str:
       ...
   ```

2. **Add new API endpoint**:
   ```python
   class CallAggregateReq(BaseModel):
       project_id: str
       call_id: str
       feedback_type: str
       aggregation: str = "mean"
       include_self: bool = True
   ```

3. **Benchmark** on real trace data to establish performance baselines.

### Phase 2: Path Materialization (if needed for performance)

If Phase 1 shows unacceptable latency:

1. Add `path` column to `calls_complete`
2. Populate path on call insert/start
3. Create migration to backfill existing data
4. Update aggregation queries to use path-based filtering

### Phase 3: Pre-computed Aggregates (for high-volume use cases)

If real-time aggregates are needed at scale:

1. Create `call_score_aggregates` table
2. Implement cascade update logic
3. Background job for eventual consistency

## Performance Considerations

| Approach | Write Impact | Read Latency | Memory | Complexity |
|----------|-------------|--------------|--------|------------|
| Recursive CTE | None | O(tree_size) | High | Low |
| Materialized Path | Low | O(subtree) | Low | Medium |
| Pre-computed | High | O(1) | Low | High |
| Hybrid Cache | None | O(1) cached | Medium | Medium |

**Benchmarking Recommendations**:
- Test with traces of depth 10, 50, 100
- Test with branching factor 2, 5, 10
- Measure: query latency, memory usage, CPU time

## Revised Recommendation Given ClickHouse Constraints

Based on the analysis, here's what's **actually feasible** in ClickHouse:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        FEASIBILITY ASSESSMENT                               │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  Recursive CTE          ✓ WORKS - but requires enable_analyzer setting     │
│                           and has depth/performance limits                  │
│                                                                             │
│  Materialized Path      ✓ WORKS - has() function exists and uses indexes  │
│                           Requires schema change + backfill                 │
│                                                                             │
│  Pre-computed Aggs      ⚠ PARTIAL - AggregatingMergeTree works, BUT        │
│  (via MV auto-cascade)    cascade must be done in APPLICATION CODE         │
│                           ClickHouse MV cannot do multi-row fan-out        │
│                                                                             │
│  Hybrid Cache           ✓ WORKS - use ClickHouse query cache or Redis     │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

**Key Insight**: The "Pre-computed Aggregates" approach is more complex than initially described
because ClickHouse cannot automatically cascade updates. You'd need:
1. Materialized path (to know ancestors without recursive query)
2. Application code that inserts N rows (one per ancestor) when feedback is added
3. AggregatingMergeTree to merge those inserts into aggregates

**Simpler Alternative**: Just use **Materialized Path + Query-time Aggregation**:
- Add `path` column to calls
- When querying aggregates: `SELECT avg(score) FROM calls WHERE has(path, 'B')`
- No complex write-time cascade needed
- Performance scales with subtree size, not total data size

## Summary: Choosing the Right Approach

```
                        READ FREQUENCY
                    Low                 High
                ┌───────────────────────────────────┐
           Low  │                                   │
                │   Recursive CTE                   │
   WRITE        │   (simplest, good enough)         │
   FREQUENCY    │                                   │
                ├───────────────────────────────────┤
           High │                                   │
                │   Materialized Path               │
                │   (good balance)                  │
                │          OR                       │
                │   Pre-computed Aggregates         │
                │   (if reads >> writes, but       │
                │    requires app-level cascade)   │
                └───────────────────────────────────┘
```

### Decision Tree

```
Start Here
    │
    ▼
┌─────────────────────────────────────┐
│ Is this an MVP / prototype?         │
└─────────────────────────────────────┘
    │ Yes                    │ No
    ▼                        ▼
┌─────────────┐    ┌─────────────────────────────────────┐
│ Use         │    │ Are traces typically < 50 nodes?    │
│ Recursive   │    └─────────────────────────────────────┘
│ CTE         │        │ Yes                    │ No
└─────────────┘        ▼                        ▼
               ┌─────────────┐    ┌─────────────────────────────────────┐
               │ Use         │    │ Is read latency critical (<10ms)?   │
               │ Recursive   │    └─────────────────────────────────────┘
               │ CTE         │        │ No                     │ Yes
               └─────────────┘        ▼                        ▼
                              ┌─────────────┐    ┌─────────────────────────────┐
                              │ Use         │    │ Can you accept eventual     │
                              │ Materialized│    │ consistency on writes?      │
                              │ Path        │    └─────────────────────────────┘
                              └─────────────┘        │ No               │ Yes
                                                     ▼                  ▼
                                             ┌─────────────┐    ┌─────────────┐
                                             │ Use         │    │ Use Pre-    │
                                             │ Materialized│    │ computed +  │
                                             │ Path +      │    │ Materialized│
                                             │ Query-time  │    │ Path (async)│
                                             │ aggregation │    └─────────────┘
                                             └─────────────┘
```

### When to Use Each

| Approach | Best For | Example Use Case |
|----------|----------|------------------|
| **Recursive CTE** | Prototyping, small traces, infrequent queries | "Show me the aggregate score for this specific trace I'm debugging" |
| **Materialized Path** | Medium traces, frequent subtree queries, need depth info | "Show aggregate scores at each depth level in my evaluation" |
| **Pre-computed** | Large scale, real-time dashboards, high read volume | "Dashboard showing aggregate quality across all traces, updated live" |
| **Hybrid Cache** | Bursty access patterns, tolerance for slight staleness | "Popular traces queried frequently, long-tail rarely accessed" |

### Recommended Evolution Path

```
Phase 1: MVP                    Phase 2: Scale              Phase 3: Production
─────────────────────────────────────────────────────────────────────────────────

┌─────────────────┐            ┌─────────────────┐         ┌─────────────────┐
│ Recursive CTE   │            │ + Materialized  │         │ + Pre-computed  │
│                 │ ────────►  │   Path          │ ──────► │   Aggregates    │
│ (No schema      │            │                 │         │                 │
│  changes)       │            │ (Schema         │         │ (New table +    │
│                 │            │  migration)     │         │  cascade logic) │
└─────────────────┘            └─────────────────┘         └─────────────────┘

Trigger: Latency > 100ms       Trigger: Latency > 10ms    Trigger: Need real-time
         on typical traces              or high QPS               dashboards
```

## Implementation: Recursive CTE for Weave Data Model

This section provides concrete implementation details for the recursive CTE approach,
specifically tailored to the Weave call and feedback data model.

### Current Python Implementation: `sum_dict_leaves`

Today, summary rollup is done client-side in Python using `sum_dict_leaves`:

```python
# weave/trace/weave_client.py:863-867
computed_summary: dict[str, Any] = {}
if call._children:
    computed_summary = sum_dict_leaves(
        [child.summary or {} for child in call._children]
    )
```

The function recursively combines dictionaries by summing numeric leaves:

```python
# Example: Rolling up LLM usage across child calls
children_summaries = [
    {"usage": {"gpt-4": {"requests": 1, "prompt_tokens": 100, "completion_tokens": 50}}},
    {"usage": {"gpt-4": {"requests": 2, "prompt_tokens": 200, "completion_tokens": 100}}},
    {"usage": {"gpt-3.5": {"requests": 1, "prompt_tokens": 50, "completion_tokens": 25}}},
]
# Result:
# {
#   "usage": {
#     "gpt-4": {"requests": 3, "prompt_tokens": 300, "completion_tokens": 150},
#     "gpt-3.5": {"requests": 1, "prompt_tokens": 50, "completion_tokens": 25}
#   }
# }
```

### Challenge: Translating to ClickHouse

The Python approach has these characteristics:
1. **Arbitrary nesting depth** - handles any JSON structure
2. **Dynamic keys** - doesn't require knowing field names ahead of time
3. **Type coercion** - sums numbers, collects non-numbers into lists

ClickHouse SQL requires a more structured approach:
1. **Known fields** - must specify which JSON paths to extract
2. **Fixed types** - must declare types for extraction
3. **Explicit aggregation** - must use aggregate functions

### Approach: Schema-Aware Aggregation

Rather than trying to replicate arbitrary `sum_dict_leaves` in SQL, we define **specific aggregation targets**:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    WHAT WE WANT TO AGGREGATE                                │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  1. LLM Usage (from summary_dump):                                         │
│     - summary.usage.{model}.requests                                       │
│     - summary.usage.{model}.prompt_tokens                                  │
│     - summary.usage.{model}.completion_tokens                              │
│     - summary.usage.{model}.total_tokens                                   │
│                                                                             │
│  2. Status Counts (from summary_dump):                                     │
│     - summary.weave.status_counts_by_op.{op_name}.SUCCESS                 │
│     - summary.weave.status_counts_by_op.{op_name}.ERROR                   │
│                                                                             │
│  3. Feedback Scores (from feedback table):                                 │
│     - feedback.payload.value (for simple scores)                           │
│     - feedback.payload.output.{field} (for scorer outputs)                │
│                                                                             │
│  4. Latency (from call fields):                                            │
│     - ended_at - started_at                                                │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Example 1: Aggregate LLM Usage Across a Subtree

This query aggregates token usage for all calls under a specific call:

```sql
-- Required setting for recursive CTEs
SET enable_analyzer = 1;

WITH RECURSIVE
-- Step 1: Find all descendants of the target call
descendants AS (
    -- Base case: the target call itself
    SELECT
        id,
        parent_id,
        summary_dump,
        0 AS depth
    FROM calls_complete
    WHERE project_id = {project_id:String}
      AND id = {root_call_id:String}

    UNION ALL

    -- Recursive case: find children
    SELECT
        c.id,
        c.parent_id,
        c.summary_dump,
        d.depth + 1
    FROM calls_complete c
    INNER JOIN descendants d ON c.parent_id = d.id
    WHERE c.project_id = {project_id:String}
      AND d.depth < 100  -- Safety limit
),

-- Step 2: Extract usage data from each call's summary
usage_extracted AS (
    SELECT
        id,
        depth,
        -- Extract the usage JSON object
        ifNull(JSONExtractRaw(summary_dump, 'usage'), '{}') AS usage_raw
    FROM descendants
    WHERE usage_raw != '' AND usage_raw != '{}'
),

-- Step 3: Explode usage by model (each model becomes a row)
usage_by_model AS (
    SELECT
        id,
        depth,
        kv.1 AS model_id,
        JSONExtractInt(kv.2, 'requests') AS requests,
        JSONExtractInt(kv.2, 'prompt_tokens') AS prompt_tokens,
        JSONExtractInt(kv.2, 'completion_tokens') AS completion_tokens,
        JSONExtractInt(kv.2, 'total_tokens') AS total_tokens
    FROM usage_extracted
    ARRAY JOIN JSONExtractKeysAndValuesRaw(usage_raw) AS kv
)

-- Step 4: Aggregate across all descendants, grouped by model
SELECT
    model_id,
    sum(requests) AS total_requests,
    sum(prompt_tokens) AS total_prompt_tokens,
    sum(completion_tokens) AS total_completion_tokens,
    sum(total_tokens) AS total_total_tokens,
    count() AS call_count
FROM usage_by_model
GROUP BY model_id
ORDER BY total_requests DESC;
```

**Result example:**
```
┌─model_id────────┬─total_requests─┬─total_prompt_tokens─┬─total_completion_tokens─┐
│ gpt-4           │ 15             │ 3500                │ 1200                    │
│ gpt-3.5-turbo   │ 42             │ 8200                │ 4100                    │
│ claude-3-sonnet │ 8              │ 2100                │ 950                     │
└─────────────────┴────────────────┴─────────────────────┴─────────────────────────┘
```

### Example 2: Aggregate Feedback Scores Across a Subtree

This query aggregates feedback scores for all calls under a specific call:

```sql
SET enable_analyzer = 1;

WITH RECURSIVE
-- Step 1: Find all descendants
descendants AS (
    SELECT id, parent_id, 0 AS depth
    FROM calls_complete
    WHERE project_id = {project_id:String}
      AND id = {root_call_id:String}

    UNION ALL

    SELECT c.id, c.parent_id, d.depth + 1
    FROM calls_complete c
    INNER JOIN descendants d ON c.parent_id = d.id
    WHERE c.project_id = {project_id:String}
      AND d.depth < 100
),

-- Step 2: Join with feedback table
feedback_joined AS (
    SELECT
        d.id AS call_id,
        d.depth,
        f.feedback_type,
        f.payload_dump
    FROM descendants d
    INNER JOIN feedback f ON f.weave_ref = concat('weave:///', {project_id:String}, '/call/', d.id)
    WHERE f.project_id = {project_id:String}
)

-- Step 3: Aggregate by feedback type
SELECT
    feedback_type,
    count() AS feedback_count,
    avg(JSONExtractFloat(payload_dump, 'value')) AS avg_score,
    min(JSONExtractFloat(payload_dump, 'value')) AS min_score,
    max(JSONExtractFloat(payload_dump, 'value')) AS max_score,
    sum(JSONExtractFloat(payload_dump, 'value')) AS sum_score
FROM feedback_joined
WHERE JSONHas(payload_dump, 'value')
GROUP BY feedback_type
ORDER BY feedback_count DESC;
```

**Result example:**
```
┌─feedback_type─────────────────┬─feedback_count─┬─avg_score─┬─min_score─┬─max_score─┐
│ wandb.runnable.quality_scorer │ 23             │ 0.78      │ 0.2       │ 1.0       │
│ thumbs_up                     │ 15             │ 1.0       │ 1.0       │ 1.0       │
│ accuracy                      │ 12             │ 0.85      │ 0.5       │ 0.98      │
└───────────────────────────────┴────────────────┴───────────┴───────────┴───────────┘
```

### Example 3: Aggregate Latency Statistics

```sql
SET enable_analyzer = 1;

WITH RECURSIVE
descendants AS (
    SELECT id, parent_id, started_at, ended_at, op_name, 0 AS depth
    FROM calls_complete
    WHERE project_id = {project_id:String}
      AND id = {root_call_id:String}

    UNION ALL

    SELECT c.id, c.parent_id, c.started_at, c.ended_at, c.op_name, d.depth + 1
    FROM calls_complete c
    INNER JOIN descendants d ON c.parent_id = d.id
    WHERE c.project_id = {project_id:String}
      AND d.depth < 100
)

SELECT
    op_name,
    count() AS call_count,
    avg(dateDiff('millisecond', started_at, ended_at)) AS avg_latency_ms,
    min(dateDiff('millisecond', started_at, ended_at)) AS min_latency_ms,
    max(dateDiff('millisecond', started_at, ended_at)) AS max_latency_ms,
    quantile(0.5)(dateDiff('millisecond', started_at, ended_at)) AS p50_latency_ms,
    quantile(0.95)(dateDiff('millisecond', started_at, ended_at)) AS p95_latency_ms
FROM descendants
WHERE ended_at IS NOT NULL
GROUP BY op_name
ORDER BY call_count DESC;
```

### Example 4: Combined Rollup (Usage + Feedback + Latency)

For a comprehensive rollup similar to `sum_dict_leaves`, we can combine multiple aggregations:

```sql
SET enable_analyzer = 1;

WITH RECURSIVE
descendants AS (
    SELECT
        id,
        parent_id,
        op_name,
        started_at,
        ended_at,
        summary_dump,
        0 AS depth
    FROM calls_complete
    WHERE project_id = {project_id:String}
      AND id = {root_call_id:String}

    UNION ALL

    SELECT
        c.id,
        c.parent_id,
        c.op_name,
        c.started_at,
        c.ended_at,
        c.summary_dump,
        d.depth + 1
    FROM calls_complete c
    INNER JOIN descendants d ON c.parent_id = d.id
    WHERE c.project_id = {project_id:String}
      AND d.depth < 100
),

-- Aggregate latency by depth level
latency_by_depth AS (
    SELECT
        depth,
        count() AS call_count,
        sum(dateDiff('millisecond', started_at, ended_at)) AS total_latency_ms
    FROM descendants
    WHERE ended_at IS NOT NULL
    GROUP BY depth
),

-- Aggregate usage (flattened)
usage_agg AS (
    SELECT
        kv.1 AS model_id,
        sum(JSONExtractInt(kv.2, 'requests')) AS requests,
        sum(JSONExtractInt(kv.2, 'prompt_tokens')) AS prompt_tokens,
        sum(JSONExtractInt(kv.2, 'completion_tokens')) AS completion_tokens
    FROM descendants
    ARRAY JOIN JSONExtractKeysAndValuesRaw(
        ifNull(JSONExtractRaw(summary_dump, 'usage'), '{}')
    ) AS kv
    WHERE kv.1 != ''
    GROUP BY model_id
),

-- Aggregate feedback
feedback_agg AS (
    SELECT
        f.feedback_type,
        count() AS count,
        avg(JSONExtractFloat(f.payload_dump, 'value')) AS avg_value
    FROM descendants d
    INNER JOIN feedback f ON f.weave_ref = concat('weave:///', {project_id:String}, '/call/', d.id)
    WHERE f.project_id = {project_id:String}
      AND JSONHas(f.payload_dump, 'value')
    GROUP BY f.feedback_type
)

-- Return all aggregations
SELECT 'summary' AS section, * FROM (
    SELECT
        count() AS total_calls,
        max(depth) AS max_depth,
        sum(total_latency_ms) AS total_latency_ms
    FROM latency_by_depth
)
UNION ALL
SELECT 'usage' AS section, * FROM usage_agg
UNION ALL
SELECT 'feedback' AS section, * FROM feedback_agg;
```

### Handling Dynamic/Nested Keys

For truly dynamic JSON structures (like arbitrary scorer outputs), use `JSONExtractKeysAndValuesRaw`:

```sql
-- Extract all keys from a nested JSON path
SELECT
    call_id,
    kv.1 AS metric_name,
    kv.2 AS metric_value_raw,
    JSONExtractFloat(kv.2) AS metric_value_float
FROM feedback_joined
ARRAY JOIN JSONExtractKeysAndValuesRaw(
    JSONExtractRaw(payload_dump, 'output')
) AS kv
WHERE kv.1 NOT IN ('_type', '__class__')  -- Filter out metadata keys
```

### Performance Considerations

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    PERFORMANCE CHARACTERISTICS                              │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  Recursive CTE Cost:                                                        │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ Tree Size │ Iterations │ Memory   │ Expected Latency               │   │
│  ├───────────┼────────────┼──────────┼────────────────────────────────┤   │
│  │ 10 nodes  │ ~3-4       │ Low      │ < 10ms                         │   │
│  │ 100 nodes │ ~5-7       │ Medium   │ 10-50ms                        │   │
│  │ 1000 nodes│ ~10-12     │ High     │ 50-200ms                       │   │
│  │ 10k nodes │ ~15+       │ Very High│ 200ms-1s (may need limits)     │   │
│  └───────────┴────────────┴──────────┴────────────────────────────────┘   │
│                                                                             │
│  JSON Extraction Cost (per row):                                           │
│  - JSONExtractRaw: Fast (string slice)                                     │
│  - JSONExtractInt/Float: Medium (parse + extract)                          │
│  - JSONExtractKeysAndValuesRaw: Slow (full parse + iterate)               │
│                                                                             │
│  Optimization Tips:                                                         │
│  1. Add depth limit to recursive CTE (d.depth < N)                         │
│  2. Filter early in base case (by trace_id, time range)                    │
│  3. Use bloom filter index on parent_id for faster joins                   │
│  4. Consider materialized path for frequent queries                        │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### When to Use Query-Time vs Pre-Computed

| Use Case | Approach | Rationale |
|----------|----------|-----------|
| Debugging a specific trace | Query-time CTE | Rare, ad-hoc query |
| Dashboard showing trace summary | Query-time CTE + cache | Moderate frequency, acceptable latency |
| Real-time aggregate metrics | Materialized path + query-time | Need <10ms response |
| Billing/cost reports | Pre-computed aggregates | High accuracy, batch update OK |
| ML evaluation rollups | Query-time CTE | Complex, varies per evaluation |

### Existing Pattern: Token Cost Calculation

The codebase already uses a similar pattern for token cost aggregation:

```python
# weave/trace_server/token_costs.py:133-150
usage_raw = "ifNull(JSONExtractRaw(summary_dump, 'usage'), '{}') AS usage_raw"
kv = f"""arrayJoin(
    if(usage_raw != '' and usage_raw != '{{}}',
    JSONExtractKeysAndValuesRaw(usage_raw),
    [('{DUMMY_LLM_ID}', '{ESCAPED_DUMMY_LLM_USAGE}')])
) AS kv"""
llm_id = "kv.1 AS llm_id"
requests = "JSONExtractInt(kv.2, 'requests') AS requests"
prompt_tokens = """if(JSONHas(kv.2, 'prompt_tokens'),
    JSONExtractInt(kv.2, 'prompt_tokens'),
    JSONExtractInt(kv.2, 'input_tokens')) AS prompt_tokens"""
```

This pattern can be extended to work with recursive CTEs.

## Verified Working Query

This section documents the **verified working** recursive CTE with feedback join, tested against production data.

### Critical Discovery: weave_ref Format

**IMPORTANT**: The feedback table uses a different URI format than initially documented:

```
Expected format:  weave:///PROJECT_ID/call/CALL_ID
Actual format:    weave-trace-internal:///PROJECT_ID/call/CALL_ID
```

This was discovered through testing. Always verify the actual `weave_ref` format in your database.

### Working Query: Aggregate Feedback Across Trace Subtree

```sql
-- Required: Enable the new query analyzer for recursive CTE support
SET enable_analyzer = 1;

WITH RECURSIVE
tree AS (
    -- Base case: start from a specific call
    SELECT id, parent_id, op_name, 1 AS depth
    FROM calls_merged
    WHERE project_id = 'YOUR_PROJECT_ID'
      AND id = 'YOUR_ROOT_CALL_ID'

    UNION ALL

    -- Recursive case: find all children
    SELECT c.id, c.parent_id, c.op_name, t.depth + 1
    FROM calls_merged c
    INNER JOIN tree t ON c.parent_id = t.id
    WHERE c.project_id = 'YOUR_PROJECT_ID'
      AND t.depth < 50  -- Safety limit to prevent runaway recursion
)
SELECT
    feedback_type,
    count() AS total_feedback,
    countIf(JSONExtractBool(payload_dump, 'output') = true) AS true_count,
    countIf(JSONExtractBool(payload_dump, 'output') = false) AS false_count,
    round(countIf(JSONExtractBool(payload_dump, 'output') = true) / count() * 100, 2) AS true_percentage
FROM tree t
INNER JOIN feedback f
    ON f.weave_ref = concat('weave-trace-internal:///', 'YOUR_PROJECT_ID', '/call/', t.id)
    AND f.project_id = 'YOUR_PROJECT_ID'
GROUP BY feedback_type
ORDER BY total_feedback DESC;
```

### Key Differences from Initial Design

| Aspect | Initial Design | Verified Working |
|--------|---------------|------------------|
| Table | `calls_complete` | `calls_merged` |
| weave_ref format | `weave:///` | `weave-trace-internal:///` |
| Feedback payload | `JSONExtractFloat(payload_dump, 'value')` | `JSONExtractBool(payload_dump, 'output')` (varies by feedback type) |
| Depth column | `0 AS depth` (0-indexed) | `1 AS depth` (1-indexed) |

### Payload Format Variations

Feedback payloads vary by type. Common formats observed:
- **Boolean scores**: `{"output": true}` or `{"output": false}`
- **Numeric scores**: `{"value": 0.85}`
- **Scorer outputs**: `{"output": {"score": 0.9, "reasoning": "..."}}`

Adjust the `JSONExtract*` function based on your feedback type's payload structure.

## Efficiency Analysis for Long Traces

### Time Complexity

The recursive CTE approach has the following complexity characteristics:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    TIME COMPLEXITY ANALYSIS                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  Recursive CTE Execution Model:                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                                                                     │   │
│  │  Iteration 1: Find root node (base case)          O(1) lookup      │   │
│  │  Iteration 2: Find root's children               O(n) scan         │   │
│  │  Iteration 3: Find grandchildren                 O(n) scan         │   │
│  │  ...                                                               │   │
│  │  Iteration D: Find nodes at depth D             O(n) scan         │   │
│  │                                                                     │   │
│  │  Total iterations = max_depth of tree = D                          │   │
│  │  Each iteration scans calls table filtered by project_id           │   │
│  │                                                                     │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│  Overall: O(D × N_project) where:                                          │
│    D = maximum depth of the trace tree                                      │
│    N_project = total calls in the project (filtered by project_id index)   │
│                                                                             │
│  With proper indexing on (project_id, parent_id), this becomes:            │
│    O(D × branch_factor) ≈ O(tree_size)                                     │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Memory Complexity

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    MEMORY COMPLEXITY ANALYSIS                                │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  Recursive CTE Memory Model:                                                │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                                                                     │   │
│  │  The CTE materializes ALL intermediate results in memory:          │   │
│  │                                                                     │   │
│  │  Memory = sum of all rows across all iterations                    │   │
│  │         = total nodes in subtree × bytes per row                   │   │
│  │                                                                     │   │
│  │  For our query (id, parent_id, op_name, depth):                    │   │
│  │    ~100-200 bytes per row (UUIDs + string + int)                   │   │
│  │                                                                     │   │
│  │  Estimated memory by tree size:                                     │   │
│  │    100 nodes   → ~20 KB                                            │   │
│  │    1,000 nodes → ~200 KB                                           │   │
│  │    10,000 nodes → ~2 MB                                            │   │
│  │    100,000 nodes → ~20 MB                                          │   │
│  │                                                                     │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│  Overall: O(tree_size) memory                                              │
│                                                                             │
│  Note: If selecting large columns (summary_dump, inputs_dump), memory      │
│  grows significantly. Our query is optimized by selecting only needed cols.│
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Feedback Join Cost

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    FEEDBACK JOIN COST ANALYSIS                               │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  The feedback table join adds significant cost:                             │
│                                                                             │
│  Current approach (string concatenation + equality):                        │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                                                                     │   │
│  │  ON f.weave_ref = concat('weave-trace-internal:///', project, ...)  │   │
│  │                                                                     │   │
│  │  This requires:                                                      │   │
│  │  1. Building the weave_ref string for each tree node               │   │
│  │  2. Hash lookup in feedback table (if indexed on weave_ref)        │   │
│  │                                                                     │   │
│  │  Cost per node: O(1) with index, O(N_feedback) without             │   │
│  │  Total cost: O(tree_size) with index                               │   │
│  │                                                                     │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│  Optimization opportunity: If feedback table has index on                   │
│  (project_id, weave_ref), the join is efficient. Verify with:              │
│                                                                             │
│  SHOW CREATE TABLE feedback;                                                │
│  -- Look for ORDER BY clause including weave_ref                           │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Scalability Projections

| Tree Size | Expected Latency | Memory Usage | Recommended Approach |
|-----------|-----------------|--------------|---------------------|
| < 100 nodes | < 50ms | < 100 KB | Recursive CTE (current) |
| 100-1,000 nodes | 50-200ms | 100 KB - 1 MB | Recursive CTE with depth limit |
| 1,000-10,000 nodes | 200ms-1s | 1-10 MB | Materialized path recommended |
| > 10,000 nodes | > 1s | > 10 MB | Pre-computed aggregates required |

### Bottlenecks for Large Traces

1. **Iteration Count**: Each depth level requires a full iteration. Deep trees (D > 50) will have many iterations.

2. **Parent ID Lookup**: The `c.parent_id = t.id` join must scan `calls_merged` for each iteration. Without a proper index on `parent_id`, this becomes O(N) per iteration.

3. **Memory Pressure**: All intermediate results are held in memory. For trees with 10,000+ nodes, this can cause memory pressure.

4. **Feedback Table Size**: If the feedback table is large and not properly indexed on `weave_ref`, the join becomes the bottleneck.

### Optimization Recommendations

```sql
-- 1. Add depth limit to prevent runaway queries
AND t.depth < 50  -- Already included in our query

-- 2. Filter by trace_id in base case if known (reduces initial scan)
WHERE project_id = '...'
  AND id = '...'
  AND trace_id = '...'  -- Add if trace_id is known

-- 3. Select only columns needed (don't fetch summary_dump unless required)
SELECT id, parent_id, op_name, depth  -- Minimal columns

-- 4. Consider adding index on parent_id if not exists
-- (Check current indexes: SHOW CREATE TABLE calls_merged)

-- 5. For very large trees, switch to materialized path approach
-- (See "Approach 2: Materialized Path Pattern" section above)
```

### When to Switch Approaches

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    DECISION MATRIX FOR APPROACH SELECTION                    │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  Query latency < 100ms AND tree size < 1000?                               │
│    → Stay with recursive CTE (simplest, no schema changes)                  │
│                                                                             │
│  Query latency 100-500ms AND tree size 1000-10000?                         │
│    → Add materialized path column for O(1) subtree queries                 │
│    → Keep recursive CTE as fallback for edge cases                         │
│                                                                             │
│  Query latency > 500ms OR tree size > 10000?                               │
│    → Implement pre-computed aggregates with application-level cascade      │
│    → Use materialized path to identify ancestors during cascade            │
│                                                                             │
│  Read frequency >> Write frequency (dashboards, reports)?                  │
│    → Strongly favor pre-computed aggregates                                │
│    → Accept eventual consistency for faster reads                          │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Open Questions

1. **Aggregation Functions**: Which are required?
   - `mean`, `sum`, `min`, `max`, `count`
   - Weighted averages?
   - Percentiles?

2. **Scope Control**: Should users be able to specify:
   - Depth limit (e.g., only direct children)?
   - Filter by op_name?
   - Filter by time range?

3. **Multiple Score Types**: How to handle aggregating multiple feedback types simultaneously?

4. **Null Handling**: How to treat calls without scores?
   - Exclude from aggregation?
   - Default value?

5. **Real-time vs Batch**: Is real-time aggregation required, or can we accept eventual consistency?

## References

- [ClickHouse WITH Clause Documentation](https://clickhouse.com/docs/sql-reference/statements/select/with)
- [ClickHouse Release 24.4 - Recursive CTE Support](https://clickhouse.com/blog/clickhouse-release-24-04)
- [Cascading Materialized Views](https://clickhouse.com/docs/guides/developer/cascading-materialized-views)
- [Using Materialized Views in ClickHouse](https://clickhouse.com/blog/using-materialized-views-in-clickhouse)
- Existing recursive CTE usage: `weave/trace_server/sqlite_trace_server.py:742`
