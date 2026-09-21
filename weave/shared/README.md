# Shared definitions

`trace_server/` owns portable trace API models, validation, errors, IDs and
reference conversion. Both the SDK and backend use these definitions. It must
not import SDK execution or backend implementation modules.

The matching `weave.trace_server` modules re-export these definitions for existing
imports. Exception classes and the ignored-field warning cache retain one identity.
HTTP and ClickHouse exception translation and ClickHouse row models remain in the
backend. The executable builtin model and its registry are not moved in this step.

This extraction preserves the request/response schemas from Weave revision
`648c39783259b2981a08fadbd2daeedeffa4eef6`. The original MIT license applies.
