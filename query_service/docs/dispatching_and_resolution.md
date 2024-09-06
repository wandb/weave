# Dispatching and Resolution

The overall dispatch and resolution flow works as follows (pictured in the diagram below):

1. When constructing a graph in python, the user will write something like `node.foo` or `node.foo()`. In both cases the Python runtime will ask `node` to resolve the symbol `foo`. If `foo` is found in the MRO (faciliated by the mix-ins in `lazy.py`), then that is returned. Else, we get to the base `FallbackNodeTypeDispatcherMixin` class which will attempt to resolve `foo` dynamically.
2. (First dispatch-like logic): At this point, we take the type of `node` (already known) and look for any op ending in `foo` which would accept the type of `node`. We return the first one found. If none is found, we return the opGetAttr op assuming `foo` is an attribute of the type.
3. From there, the returned op for `foo` is called with any params. This follows `__call__` -> `lazy_call` path in OpDef.
   4.(Second dispatch-like logic) Here, we must convert the arguments to nodes (and by definition, determine their types). This is expensive, but required. At this point in time, it is possible that the opDef being called is not the correct op def (this is the case when the first param and the common name is the same, but the op resolution needs to look at the rest of the params). Here we call `dispatch.py::get_op_for_input_types` to determine the correct opDef to use, then constuct the output node.
4. Now, consider that the user calls `use(node.foo())` - or, equivilently, a request comes in from the UI with a node payload. In this case, we enter the execute path.
5. (Third dispatch-like logic) Before running the graph, we compile it in `compile.py`. One step: `compile::apply_type_based_dispatch`, will look at the common name of the ops in the graph and attempt to replace them with the correct op based on the types of the inputs. This is fast since the types are known. True, this is a bit duplicative for graphs constructed in python, but that should be ok. In addition mappability, this step implicitly handles JSList interface conversion. Since the target ops have the same common name, they are automatically replaced with their type-specific counterparts.
6. Finally, the graph is executed.

```mermaid
flowchart
    subgraph python graph construction
    A[node.foo] --> B{`foo` in mixin MRO?}
    B --> |No| C[FallbackNodeTypeDispatcherMixin.__getattr__]
    B --> |Yes| D[foo.__call__]
    C --> E{'foo' candidate op found?<br>mem_reg::find_ops_by_common_name}
    E --> |No| F[Return opGetAttr node, 'foo']
    E --> |Yes| G[Return opFoo bound to node]
    G --> D
    D --> H[lazy.py::lazy_call]
    H --> I[Convert args to nodes - expensive]
    I --> J[dispatch.py::get_op_for_input_types]
    J --> J1{Dispatch Op Found?}
    J1 --> |No| J1N[Construct output node with foo op as fallback]
    J1 --> |Yes| J1Y[Construct output node found op]
    J1N --> K[Return outputnode with dispatched op]
    J1Y --> K
    end
    K --> L[use node.foo]
    L --> M[execute.execute_nodes]
    subgraph JS graph construction
    Z[server gets JS request] --> Y[server.execute]
    end
    Y --> M
    M --> N[compile.compile]
    N --> O[compile::apply_type_based_dispatch]
    O --> P[inexpensive, order-based arg binding<br>dispatch.py::get_op_for_input_types]
    P --> Q{Dispatched op found?<br>eg. mapped / js list interface resolved}
    Q --> |Yes| S[Replace node]
    S --> R[Forward Resolution]
    Q --> |No| R
```
