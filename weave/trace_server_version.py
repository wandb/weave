# =============================================================================
# TRACE SERVER VERSION HANDSHAKE (Client Side)
# =============================================================================
#
# This version handshake enables compatibility checking between the weave client
# and trace server. At startup, the client fetches /server_info which returns:
#   - min_required_weave_python_version: minimum client version the server requires
#   - trace_server_version: the server's current version
#
# The client then performs two checks:
#   1. Is my version >= server's min_required_weave_python_version?
#   2. Is server's trace_server_version >= my MIN_TRACE_SERVER_VERSION?
#
# If either check fails, the client raises an error at startup with instructions
# to upgrade either the client or server.
#
# WHEN TO SET MIN_TRACE_SERVER_VERSION:
#   - When this client version depends on server features added in a specific version
#   - Example: Client calls a new endpoint only available in server >= 0.2.0
#   - Example: Client expects a response field only returned by server >= 0.3.0
#
# WHEN TO LEAVE AS None:
#   - When the client is compatible with all server versions
#   - When you want maximum backwards compatibility with older on-prem deployments
#
# IMPORTANT: Setting this to a non-None value means users with older servers
# (primarily on-prem deployments) will be blocked from using this client version
# until they upgrade their server.
#
# Use semantic versioning: "MAJOR.MINOR.PATCH" (e.g., "0.1.0", "1.0.0")
# =============================================================================
MIN_TRACE_SERVER_VERSION: str | None = None
