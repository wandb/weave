# Turn metrics on signature rows

Every `turn_` column in the insights tables describes a whole turn, and every table
stores more than one row per turn. Summing one of those columns therefore counts a
turn once per row rather than once. The duplication is in the row grain, so the tables
carry `turn_signature_count` as the divisor that makes the sum correct again.

## Where the fan-out comes from

```
turn (one trace_id)
└── judge emits 1..N signatures        intent: max_items_per_turn = 8
    └── clustering emits one assignment per signature
```

One turn that cost $0.20 and produced three intents becomes three
`intent_signatures` rows carrying `turn_cost_usd = 0.20`, then three
`signature_cluster_assignments` rows carrying the same value. The same holds for
`turn_duration_ms` and all five token columns. `turn_signature_count` is 3 on every
one of those rows.

## What each aggregate answers

Three turns costing $0.10, $0.20 and $0.30. The project spent **$0.60**. Turn 1
produced three intents (two in cluster A, one in B), turn 2 one intent (A), turn 3
two intents (both B).

| Cluster | `sum(turn_cost_usd)` | attributed | apportioned | `uniqExact(trace_id)` |
| --- | --- | --- | --- | --- |
| A | 0.40 | 0.30 | 0.2667 | 2 |
| B | 0.70 | 0.40 | 0.3333 | 2 |
| **total** | **1.10** | **0.70** | **0.60** | **3** |

- **Naive `sum`** inflates by the fan-out factor, here 1.83x and up to 8x. It answers
  no question. Never ship it.
- **Apportioned** splits a turn's value evenly across its signatures. The only form
  that sums back to the project total, so it is the default for any chart whose parts
  should add up.
- **Attributed** credits a turn's full value to every cluster it touched. Correct per
  cluster and deliberately not additive, because turn 1 belongs to both. Read it as
  "turns touching this topic cost $X".
- **Turn count** is exact and needs no divisor.

```sql
-- Apportioned: additive, no subquery.
SELECT cluster_id, sum(turn_cost_usd / turn_signature_count)
FROM signature_cluster_assignments
WHERE project_id = {project_id:String} AND cluster_run_id = {run_id:UUID}
GROUP BY cluster_id

-- Attributed: collapse to one row per turn first.
SELECT cluster_id, sum(cost)
FROM (
    SELECT cluster_id, trace_id, any(turn_cost_usd) AS cost
    FROM signature_cluster_assignments
    WHERE project_id = {project_id:String} AND cluster_run_id = {run_id:UUID}
    GROUP BY cluster_id, trace_id
)
GROUP BY cluster_id
```

`turn_signature_count` defaults to 1, so a writer that never sets it degrades to the
naive sum rather than dividing by zero. `signature_clusters.occurrence_count` counts
signatures, not turns, and is inflated against `uniqExact(trace_id)` by the same
factor.

## Both signature types mean the same thing

`intent_signatures.turn_cost_usd` is the cost of the turn in `trace_id`.
`failure_signatures.turn_cost_usd` is the cost of the turn in `current_trace_id`. It
is not summed over `affected_trace_ids`, which 041's comment describes and 043
supersedes.

That matters because `signature_cluster_assignments` merges both types under one
column name and carries `trace_id` for intents and `current_trace_id` for failures.
Only because both are a pure function of the row's own turn can one query serve both
without branching on `signature_type`.

`affected_trace_ids` still records the turns a failure is attributed to. A total
across that set is a read-time expansion against `spans`, not a stored column, so a
multi-turn aggregate can never be mistaken for a per-turn value.

## Why dropping the columns would not help

Joining an assignment back to its signature row reproduces the identical fan-out: the
duplication lives in the one-row-per-signature grain, which both tables share. The
denormalized columns only save a join, so removing them costs a join and fixes
nothing.
