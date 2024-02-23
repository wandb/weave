# Weaveflow React Interface

This directory contains the various abstractions for working with the Weaveflow data model. This document outlines the design

I would recommend checking out the trace server data flow described in `weave/trace_server/README.md`.

At the highest level, consider that we have the following:

```mermaid
flowchart TD
    WeaveflowReactComponents --> WFReactInterfaceHooks --> WeaveflowDataProvider
```

The React application calls high-level hooks such as `useCalls` which then make queries to the appropriate data provider. Until Feb, the only data provider was Weave Compute Graph (which is backed by W&B StreamTables). However, we are introducing a new provider: Trace Server (backed by a new Clickhouse server). In the near future, we will remove parts of the Compute Graph data provider, but until then we need a nicer abstraction for working with the system. So we now have the following logical data flow:

```mermaid
flowchart TD
    WeaveflowReactComponents --> context.ts::WFDataModelHooksContext
    context.ts::WFDataModelHooksContext --> trace_server_interface::tsDataModelInterface --> trace_server_client.ts --> W&BTraceServer --> ClickHouse
    context.ts::WFDataModelHooksContext --> compute_graph_interface::cgDataModelInterface --> W&BWeaveServer --> StreamTableStorage
```

The dependencies are laid out like:

```mermaid
flowchart TD
    cache.ts --> interface.ts

    compute_graph_interface.ts --> utilities.ts
    compute_graph_interface.ts --> interface.ts
    compute_graph_interface.ts --> constants.ts
    compute_graph_interface.ts --> cache.ts

    interface.ts --> constants.ts

    context.ts --> interface.ts
    context.ts --> trace_server_interface.ts
    context.ts --> compute_graph_interface.ts


    trace_server_interface.ts --> trace_server_client.ts
    trace_server_interface.ts --> utilities.ts
    trace_server_interface.ts --> interface.ts
    trace_server_interface.ts --> constants.ts
    trace_server_interface.ts --> cache.ts

    utilities.ts --> constants.ts
    utilities.ts --> interface.ts
```
