"""Server-side, client-free copy of the Content decode/MIME utilities.

Vendored from weave.type_wrappers.Content so the trace server can detect and
decode base64 / data-URI / URL payloads without importing the client SDK. The
client keeps its own copy; the two are deliberately not shared (no shared
module), per the trace-server <-> client import boundary.
"""
