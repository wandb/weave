r"""Run the mock Weave trace server.

Usage:
    python -m trace_server_mock --port=0       # ephemeral port
    python -m trace_server_mock --port=6346    # fixed port
    python -m trace_server_mock --host=0.0.0.0 --port=6346

The server prints exactly one ready-banner line to stdout before uvicorn
starts, in the form:

    READY=http://HOST:PORT

Test drivers (e.g. the Node SDK's hostApps Jest globalSetup) spawn this
module via `child_process.spawn`, capture stdout via `child.stdout.on('data', ...)`,
and parse the banner with a `READY=(\\S+)` regex to discover the URL.

The banner is printed BEFORE uvicorn binds, so callers should hit
`GET /test/health` in a short retry loop to confirm the server is actually
serving (a few iterations of ~10ms is enough). That same loop also gives
clean failure detection if uvicorn's bind fails — the driver can pair it
with a `child.on('exit')` watcher and abort with a clear error.

After the banner the process keeps running until killed.
"""

from __future__ import annotations

import argparse
import socket
import sys

import uvicorn

from .main import create_app


def main() -> None:
    parser = argparse.ArgumentParser(description="Mock Weave trace server")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument(
        "--port",
        type=int,
        default=0,
        help="Port to bind. 0 (default) picks an ephemeral port.",
    )
    args = parser.parse_args()

    # Pick an ephemeral port up front so the URL is known before uvicorn
    # starts. We bind/close a probe socket; uvicorn binds the same port a
    # moment later. There is a small race window between close and rebind,
    # but the test driver's /test/health retry loop handles it cleanly.
    if args.port == 0:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind((args.host, 0))
            port = s.getsockname()[1]
    else:
        port = args.port

    print(f"READY=http://{args.host}:{port}", flush=True)

    app = create_app()
    config = uvicorn.Config(
        app,
        host=args.host,
        port=port,
        log_level="warning",
        access_log=False,
    )
    try:
        uvicorn.Server(config).run()
    except KeyboardInterrupt:
        sys.exit(0)


if __name__ == "__main__":
    main()
