# Weave client ingest architecture

How a `@weave.op` call gets from user code to the trace server. Written as ground for the "unbounded async ingest queue + batched call_end sender" refactor.

## TL;DR
- The hot path crosses **two independent async layers** (FutureExecutor + CallBatchProcessor) before any HTTP request, plus a sync prefix in the calling thread.
- **Call starts and ends are already batched** via the `calls/complete` endpoint when `should_batch=True` (the default in `WeaveClient`). The CallBatchProcessor pairs starts with ends in memory and emits *complete* records.
- **Eager calls (`@op(eager_call_start=True)`) are not batched.** Their start fires one POST, their end fires another POST, both via `v2/call/{start,end}`. Used by `Evaluation.evaluate` and anything that needs immediate UI visibility.
- **Object saves (`obj_create`, `table_create`, `file_create`) are never batched.** Each is its own POST through the FutureExecutor pool.
- **Calling thread does meaningful sync CPU work** in `create_call`/`finish_call` (`_save_nested_objects`, `map_to_refs`, summary deepcopy, redaction, input/output `to_json`). PR #6740 moves the output-side walk into the worker pool; the input side stays sync.
- **Queues are bounded** (10K each) and drop-on-full to disk. They do **not** block the caller; defer/enqueue return immediately under saturation. So "global blocking queue" is a misnomer in this codebase, but the practical effect under sustained pressure is similar: throughput collapses or items are dropped.

## Layers (top down)

| Layer | Files | Owns |
|---|---|---|
| Decorator | `weave/trace/op.py` | sync/async/gen wrappers; entry to client |
| Client | `weave/trace/weave_client.py` | create_call, finish_call, _save_nested_objects, _save_object_basic, _save_table |
| Concurrency | `weave/trace/concurrent/futures.py` | FutureExecutor (general purpose) |
| Call batching | `weave/trace_server_bindings/call_batch_processor.py` | CallBatchProcessor (pairs starts+ends -> complete) |
| Feedback batching | `weave/trace_server_bindings/async_batch_processor.py` | AsyncBatchProcessor (used for feedback only) |
| HTTP transport | `weave/trace_server_bindings/remote_http_trace_server.py` | dispatches single vs batch endpoints |
| Oversize handling | `weave/trace_server_bindings/http_utils.py` | binary-tree split, 413 retry, repackage |
| HTTP client | `weave/utils/http_requests.py` | httpx.Client singleton; conn pool intentionally uncapped, concurrency controlled at processor layer |

## Diagram

```
                                  USER CODE
                          result = await my_op(args)
                                     |
                                     v
       +=================================================================+
       |   @weave.op wrapper  (weave/trace/op.py)                        |
       |   _call_sync_func / _call_async_func / _call_sync_gen           |
       +=================================================================+
                                     |
                                     v
       +=================================================================+
       | WeaveClient.create_call          [SYNC, calling thread]         |  (weave_client.py:903-1132)
       |  - redact_sensitive_keys(inputs)                                |
       |  - _save_nested_objects(inputs)  -- recursive Python walk;      |
       |        deferred sub-saves go to FutureExecutor (see below)      |
       |  - map_to_refs(inputs)           -- recursive Python walk       |
       |  - to_json(inputs)               -- Python tree builder;        |
       |        NO json.dumps; pydantic does that later                  |
       |  - future_executor.defer(send_start_call)  -- non-blocking      |
       +=================================================================+
                                     |
                  +------------------+------------------+
                  | (calling thread continues into the user function)
                  v
                                                                ASYNC SIDE
                                                                ----------

       +=================================================================+
       |  USER FUNCTION runs                                             |
       +=================================================================+
                                     |
                                     v
       +=================================================================+
       | WeaveClient.finish_call          [SYNC, calling thread]         |  (weave_client.py:1135-1328)
       |  - postprocess_output                                           |
       |  - _save_nested_objects(output)  ** moved off-thread by PR 6740 |
       |  - map_to_refs(output)           ** moved off-thread by PR 6740 |
       |  - copy.deepcopy(call.summary), summary merge                   |
       |  - exception_to_json_str                                        |
       |  - future_executor.defer(send_end_call)  -- non-blocking        |
       +=================================================================+


                                                  ASYNC SIDE (FutureExecutor pool)
                                                  --------------------------------

       +=================================================================+
       | FutureExecutor                                                  |  (futures.py:58-298)
       |   ContextAwareThreadPoolExecutor                                |
       |   max_workers = None  -> Python default (min(32, ncpu+4))       |
       |   internal task queue: unbounded                                |
       |   defer(): non-blocking submit -> Future                        |
       |   then(): wait on futures, then submit g                        |
       |   flush(): block until _active_futures drained                  |
       |                                                                 |
       |   Workers execute:                                              |
       |     send_start_call -> server.call_start                        |
       |     send_end_call   -> server.call_end                          |
       |     send_obj_create -> server.obj_create  (1 POST each)         |
       |     send_table_create / chunked variants                        |
       |     digest computation (post-WAL)                               |
       +=================================================================+
                                     |
                                     v
       +=================================================================+
       | RemoteHTTPTraceServer.call_start / call_end                     |  (remote_http_trace_server.py:691-717)
       |   if self.should_batch:                                         |
       |       call_processor.enqueue_start(StartBatchItem)              |  ----.
       |       OR                                                        |       \
       |       call_processor.enqueue([EndBatchItem])                    |        +--> CallBatchProcessor
       |       return synthetic CallStartRes / CallEndRes immediately    |       /
       |   else:                                                         |  ----'
       |       POST /call/start  (single record)                         |  ----.
       |       POST /call/end    (single record)                         |       +--> direct HTTP
       |                                                                 |  ----'
       |                                                                 |
       | obj_create / table_create / file_create / cost_create:          |
       |   ALWAYS direct, ONE POST per record (no batching)              |  ---->  direct HTTP
       +=================================================================+
                                     |
                  +------------------+------------------+
                  v                                     v

                                          ASYNC SIDE (CallBatchProcessor thread)
                                          ---------------------------------------

       +=================================================================+
       | CallBatchProcessor    extends AsyncBatchProcessor               |  (call_batch_processor.py:55+)
       |                                                                 |
       |   bounded Queue, maxsize=10_000  (drops to disk on full)        |
       |                                                                 |
       |   PAIRING STATE (in-memory dicts, separate from queue):         |
       |     _pending_starts: {call_id -> StartBatchItem}                |
       |     _pending_ends:   {call_id -> EndBatchItem}                  |
       |     each capped at 10_000 (RuntimeError above limit)            |
       |                                                                 |
       |   enqueue_start(start):                                         |
       |     if eager_call_start: queue as StartBatchItem (no pairing)   |
       |     elif end pending:    pair -> queue CompleteBatchItem        |
       |     else:                stash in _pending_starts               |
       |                                                                 |
       |   enqueue([end]):                                               |
       |     if start was eager: queue as EndBatchItem (no pairing)      |
       |     elif start pending: pair -> queue CompleteBatchItem         |
       |     else:               stash in _pending_ends                  |
       |                                                                 |
       |   SINGLE processing thread, ticks on:                           |
       |     batch_size >= MAX_BATCH_SIZE (1000)  OR                     |
       |     time >= min_batch_interval (1.0s)                           |
       |                                                                 |
       |   _process_mixed_batch splits into:                             |
       |     complete_items -> _flush_calls_complete                     |
       |     eager_items    -> _flush_calls_eager                        |
       |                                                                 |
       |   On flush/shutdown: wait up to 5min for pending pairs,         |
       |   then orphan-flush unpaired via v2 endpoints.                  |
       +=================================================================+
                                     |
                  +------------------+------------------+
                  v                                     v

       +================================+   +===========================================+
       | _flush_calls_complete          |   | _flush_calls_eager                        |
       |  POST /v2/{e}/{p}/calls/complete|  |  for each item:                           |
       |  body: { batch: [ ...N records ] }| |    POST /v2/{e}/{p}/call/start  (1 record)|
       |  TRUE HTTP BATCH               |   |    or                                     |
       |  413 -> binary split + retry   |   |    POST /v2/{e}/{p}/call/end    (1 record)|
       |                                |   |  NO HTTP BATCH                            |
       +================================+   +===========================================+
                  |                                       |
                  +--+                                 +--+
                     v                                 v
                                  +========================+
                                  | httpx.Client (singleton)|  (utils/http_requests.py)
                                  | unbounded conn pool     |
                                  | unbounded keepalive     |
                                  | sync POST (no asyncio)  |
                                  +========================+
                                              |
                                              v
                                  +========================+
                                  |   trace-server         |
                                  +========================+
```

## What's blocking, what isn't

- **Calling thread blocks on:** the sync prefix of `create_call` and `finish_call`. Tunable knobs today: tracing_sample_rate, `postprocess_output` to strip payload, PR #6740 (moves output-side walks off-thread).
- **`future_executor.defer(...)` does not block** the calling thread. ThreadPoolExecutor's internal queue is unbounded.
- **`call_processor.enqueue(...)` does not block** the worker. On full queue it drops to disk and logs (rate-limited).
- **The HTTP layer does not coalesce.** Each worker that lands inside `server.obj_create` / `server.table_create` issues its own POST. `requests`-style synchronous httpx; no async ingest.
- **The worker pool is the de-facto bottleneck under network latency.** That is what the prod bench showed: PR #6740's deferred CPU lands in the same pool that's already blocked on `call_start`/`call_end`/`obj_create` POSTs. No backpressure mechanism, just queue depth.

## What's already batched, what isn't

| Path | Batched at HTTP? | Endpoint |
|---|---|---|
| Normal call start+end (should_batch=True, paired) | **Yes** | `calls/complete` |
| Normal call start+end (should_batch=True, legacy) | **Yes** | `call/upsert_batch` |
| Eager call start (`@op(eager_call_start=True)`) | **No** | `v2/call/start` (1 per POST) |
| Eager call end | **No** | `v2/call/end` (1 per POST) |
| Single call_start (should_batch=False) | No | `/call/start` |
| Single call_end (should_batch=False) | No | `/call/end` |
| obj_create | **No** | `/obj/create` |
| table_create | **No** | `/table/create` |
| file_create | **No** | `/files/create` |
| feedback_create (should_batch=True) | **Yes** | `feedback/batch/create` |
| cost_create | No | `/cost/create` |

## Implications for the refactor

The user's brief was: "Replace the global blocking queue with an unbounded async ingest queue + a sender that batches call_end. we already do batching."

Three sub-claims to test, in order:

1. **The CallBatchProcessor queue is bounded (10K) but does not block; it drops.** Switching to unbounded changes the failure mode from drop-on-saturation to OOM-on-saturation, which is worse unless paired with disk/WAL backpressure. So "unbounded async ingest queue" is only safe if we add explicit backpressure (or a dedicated spill-to-disk).

2. **call_end IS batched for the normal path.** It is NOT batched for the eager path. So "a sender that batches call_end" is really "make the eager path go through the DB-friendly path whenever possible." The eager path exists because evaluations need immediate UI visibility on the start side; in practice most eager calls' ends arrive within a second of the start, so a brief hold window lets them pair into a `calls/complete` insert instead of two separate eager records.

3. **The actual prod bottleneck is worker-pool saturation under network latency.** Neither of the above directly fixes that. The real lever is widening / splitting the FutureExecutor pool, or making `server.obj_create`/`server.call_X` truly fire-and-forget (no synchronous HTTP wait inside the worker).

Concrete proposal-shapes worth scoping:

- **Batch eager-call-end** (cheapest, ships independently). Add a `_flush_call_ends_eager` that aggregates EndBatchItems by `eager_call_start=True` flag. Single new HTTP endpoint `v2/calls/end_batch` or reuse `calls/upsert_batch` semantics with end-only items. Removes the 1-POST-per-end cost for evaluations.

- **Replace the FutureExecutor's role for trace ingest with a dedicated single-purpose ingest queue.** Today FutureExecutor is shared by `send_start_call`, `send_end_call`, `send_obj_create`, `send_table_create`, digest computation, and arbitrary user-deferred work. A trace-ingest queue would: accept any (start | end | obj | table) item non-blocking; a dedicated worker thread does serialization + HTTP; backpressure spills to disk like CallBatchProcessor already does. This is essentially "extend CallBatchProcessor to also batch obj_create and table_create."

- **Decouple serialization from network.** Today the FutureExecutor worker does both. If serialization moves to its own pool/thread, network-bound work can saturate independently. Useful diagnostic before committing: how much of worker CPU is `to_json` vs httpx.post?

Pre-commit measurements I'd want before picking a shape:

- Per-worker CPU breakdown (`to_json` walk vs httpx.post vs pydantic model_dump_json) over a 30s prod bench.
- Queue depth over time in CallBatchProcessor and FutureExecutor (does either actually saturate, or just bottleneck on throughput?).
- Ratio of eager-end POSTs to complete-call POSTs in a representative evaluation workload.

The PR-6740 prod result (no win, possibly a regression) is the signal that we should not be moving more CPU into the FutureExecutor without addressing what the pool is competing on first.

---

_LAST_VERIFIED against commit `20c16d57946d4435bb4d2f9dc15b53df41da930b` (master HEAD at doc-add time). Line numbers above will rot; re-verify against current code when citing._
