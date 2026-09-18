# Built-in object validation

These models validate stored object payloads without importing SDK execution code. The shared registry is used by server object validation and client-side digest calculation. Old `weave.trace_server.interface.builtin_object_classes` paths re-export these definitions.

SDK reconstruction uses `weave.trace.base_objects.BUILTIN_OBJECT_REGISTRY`. It reuses the passive definitions except for `LLMStructuredCompletionModel`, whose executable implementation lives in `weave.flow.llm_structured_model` and still inherits directly from `Model`.

The passive LLM schema declares `_weave_serialized_bases` so `dump_object` preserves the runtime model's stored `Model`, `Object`, `BaseModel` inheritance chain. Do not infer persisted metadata from its validation-only Python base classes. The compatibility tests pin schema, normalized values and digests against the pre-split behavior.

Object-reference fields and pure validation live in `weave.shared.refs.ObjectRef`. The SDK reference extends that data class with URI handling and dereferencing. Relocatable SDK-object handling remains in `weave.object.obj.Object`; shared schemas do not load user objects.
