"""V2 Wiring — Composition Documentation

This module documents how the three v2 interface tiers compose together.
No runtime behavior — just documentation of the architecture.

Architecture
============

Three clean tiers, each with a Protocol and one or more implementations::

    WeaveClient
        |
        v
    ClientInterface (Protocol)          -- Tier 3: SDK transport
        | DirectClient | RemoteHTTPClient | CachingClient
        v
    ServiceInterface (Protocol)         -- Tier 2: Business logic
        | TraceService (delegation -> real impl)
        v
    StorageInterface (Protocol)         -- Tier 1: Data access
        | SqliteStorage | ClickHouseStorage


Tier 1: StorageInterface (Data Access)
--------------------------------------
Location: ``weave.trace_server.v2.storage_interface``

Pure data persistence. Methods map 1:1 to database queries/mutations.
Two implementations — one per supported backend:

- **SqliteStorage** — local/dev/test backend
- **ClickHouseStorage** — production backend

The storage interface does NOT handle OTEL transformation, batching,
LLM proxy calls, action execution, evaluation orchestration, or
high-level object APIs (ops, datasets, scorers, etc.).


Tier 2: ServiceInterface (Business Logic)
-----------------------------------------
Location: ``weave.trace_server.v2.service_interface``

Inherits all StorageInterface methods and adds operations that require
business logic or orchestration:

- OTEL span transformation (otel_export)
- Call batch coordination (call_start_batch, calls_complete, call_start_v2,
  call_end_v2)
- LLM proxy (completions_create, image_create)
- Action execution (actions_execute_batch)
- Evaluation orchestration (evaluate_model, evaluation_status, calls_score)
- High-level object APIs (op_*, dataset_*, scorer_*, evaluation_*, model_*,
  evaluation_run_*, prediction_*, score_*, eval_results_query)
- Service metadata (server_info, ensure_project_exists, projects_info)

One implementation:

- **TraceService** — initially delegates every method to the existing v1
  ``TraceServerInterface`` monolith (PR 3). Later replaced domain-by-domain
  with real business logic backed by StorageInterface (PR 8).


Tier 3: ClientInterface (SDK Transport)
---------------------------------------
Location: ``weave.trace_server_bindings.v2.client_interface``

The contract that ``WeaveClient`` types against. Provides the full set of
operations the SDK needs, hiding transport concerns like batching.

Three implementations:

- **DirectClient** — in-process, wraps a ServiceInterface directly.
  Used in tests: DirectClient -> TraceService -> SqliteStorage.

- **RemoteHTTPClient** — production HTTP transport. Internally uses
  AsyncBatchProcessor to batch call_start/call_end into calls_complete
  requests. The batching is invisible to the caller.

- **CachingClient** — caching middleware that wraps another ClientInterface.
  Caches read-heavy operations (obj_read, refs_read_batch, etc.).

Methods NOT on ClientInterface (hidden by transport):

- ``otel_export`` — server-to-server OTEL ingestion
- ``call_start_batch`` — server batch endpoint (used by RemoteHTTPClient)
- ``calls_complete`` — server batch endpoint (used by RemoteHTTPClient)
- ``call_start_v2`` / ``call_end_v2`` — server v2 endpoints (used by
  RemoteHTTPClient)


Production Wiring
-----------------
``weave.init()`` composes the tiers for production use::

    server = RemoteHTTPClient.from_env()
    if use_cache:
        server = CachingClient(server)
    client = WeaveClient(entity, project, server)

The server-side stack (within the trace server process)::

    HTTP router
        -> TraceService(storage=ClickHouseStorage(...))


Test Wiring
-----------
Test fixtures compose in-process without HTTP::

    storage = SqliteStorage(":memory:")
    service = TraceService(storage=storage)
    client = DirectClient(service=service)
    weave_client = WeaveClient(entity, project, client)

Or with ClickHouse::

    storage = ClickHouseStorage(connection)
    service = TraceService(storage=storage)
    client = DirectClient(service=service)
    weave_client = WeaveClient(entity, project, client)
"""
