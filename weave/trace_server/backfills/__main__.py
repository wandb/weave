"""
Entry point for running backfill CLI as a module.

Usage:
    python -m weave.trace_server.backfills <command> [options]
"""

from weave.trace_server.backfills.cli import main

if __name__ == "__main__":
    main()
