"""Standalone WAL sender — drains WAL files and replays them to the server.

Usage as a module::

    python -m weave.durability.wal_sender \\
        --entity my-entity --project my-project

Or programmatically::

    from weave.durability.wal_sender import send_wal
    send_wal(server, wal_dir)
"""

from __future__ import annotations

import argparse
import logging
import os
import sys

from weave.durability.wal import WALHandlers, WALRecord, drain_all
from weave.durability.wal_consumer import JSONLWALConsumer
from weave.durability.wal_directory_manager import FileWALDirectoryManager
from weave.trace_server import trace_server_interface as tsi
from weave.trace_server_bindings.client_interface import TraceServerClientInterface

logger = logging.getLogger(__name__)


def _build_handlers(server: TraceServerClientInterface) -> WALHandlers:
    """Build WAL record handlers that replay requests to the server."""

    def handle_obj_create(record: WALRecord) -> None:
        req = tsi.ObjCreateReq.model_validate(record["req"])
        server.obj_create(req)

    def handle_table_create(record: WALRecord) -> None:
        req = tsi.TableCreateReq.model_validate(record["req"])
        server.table_create(req)

    def handle_file_create(record: WALRecord) -> None:
        req = tsi.FileCreateReq.model_validate(record["req"])
        server.file_create(req)

    return {
        "obj_create": handle_obj_create,
        "table_create": handle_table_create,
        "file_create": handle_file_create,
    }


def send_wal(server: TraceServerClientInterface, wal_dir: str) -> int:
    """Drain all WAL files in *wal_dir*, sending each record to *server*.

    Returns the total number of records sent.
    """
    dir_mgr = FileWALDirectoryManager(wal_dir)
    handlers = _build_handlers(server)
    return drain_all(dir_mgr, handlers, JSONLWALConsumer)


def _make_server(
    trace_server_url: str, api_key: str
) -> TraceServerClientInterface:
    from weave.trace_server_bindings.remote_http_trace_server import (
        RemoteHTTPTraceServer,
    )

    return RemoteHTTPTraceServer(
        trace_server_url, auth=("api", api_key)
    )


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Drain WAL files and send records to the trace server."
    )
    parser.add_argument("--entity", required=True)
    parser.add_argument("--project", required=True)
    parser.add_argument(
        "--wal-dir",
        help="Override WAL directory (default: ~/.weave/wal/<entity>/<project>)",
    )
    parser.add_argument(
        "--trace-server-url",
        default=os.environ.get("WF_TRACE_SERVER_URL", "https://trace.wandb.ai"),
    )
    parser.add_argument(
        "--api-key",
        default=os.environ.get("WANDB_API_KEY"),
    )
    args = parser.parse_args(argv)

    if not args.api_key:
        print("Error: --api-key or WANDB_API_KEY required", file=sys.stderr)
        sys.exit(1)

    wal_dir = args.wal_dir or os.path.join(
        os.path.expanduser("~"), ".weave", "wal", args.entity, args.project
    )

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    server = _make_server(args.trace_server_url, args.api_key)
    total = send_wal(server, wal_dir)
    logger.info("Sent %d WAL records for %s/%s", total, args.entity, args.project)


if __name__ == "__main__":
    main()
