# Shared definitions

`trace_server/` owns portable trace API models, validation, errors, IDs and
reference conversion. Both the SDK and backend use these definitions. Shared
code must not import SDK execution or backend implementation modules.

Matching `weave.trace_server` modules re-export these definitions for existing
imports. Exception classes and the ignored-field warning cache retain one identity.
HTTP and ClickHouse exception translation and ClickHouse row models remain in the
backend.

## Builtin objects

The shared builtin registry contains data-only schemas. Backend normalization and
the builtin schema generator use it. The SDK registry in `weave.trace.base_objects`
contains the same schemas, except that its `LLMStructuredCompletionModel` entry is
the executable class from `weave.flow.llm_structured_model`. SDK registration must
not mutate the shared registry. Deserialization uses the SDK registry.

The schema-only model preserves the historical serialized bases
`["Model", "Object", "BaseModel"]` explicitly. Its data-only `ObjectRef` describes
the reference wire fields; it does not fetch objects or resolve SDK futures.
Message and default-parameter definitions are shared with the executable model.
The old `llm_structured_model` and `builtin_object_registry` paths remain SDK
compatibility exports, so old imports still reconstruct executable objects.
Backend code must use the shared registry rather than those two shims.

`evaluate_model_dispatcher` is the execution-independent dispatch contract.
Worker execution remains separate and uses the SDK explicitly.

These definitions originate in Weave revision
`648c39783259b2981a08fadbd2daeedeffa4eef6`. The original MIT license applies.
