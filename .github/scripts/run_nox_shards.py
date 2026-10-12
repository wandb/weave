"""Run several nox test shards side by side, one trace server each.

The servers come from WEAVE_TEST_TRACE_SERVER_URLS, which
.github/scripts/start-trace-server.sh writes. A test resets its server's whole
database, so a server serves one shard at a time. Each shard's output goes to
its own log, printed when the shard finishes. A shard that runs past
--timeout is killed, so its log still prints before the job times out.
"""

from __future__ import annotations

import argparse
import os
import queue
import signal
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("python", help="Python version of the nox sessions")
    parser.add_argument("shards", nargs="+", help="Shards, longest first")
    parser.add_argument(
        "--unfiltered",
        type=str.split,
        default=[],
        help="Shards to run without the -m trace_server filter",
    )
    parser.add_argument("--attempts", type=int, default=1)
    parser.add_argument("--timeout", type=int, default=480, help="Seconds per attempt")
    parser.add_argument("--log-dir", type=Path, required=True)
    args = parser.parse_args()

    servers: queue.Queue[str] = queue.Queue()
    for url in os.environ["WEAVE_TEST_TRACE_SERVER_URLS"].split(","):
        servers.put(url)
    args.log_dir.mkdir(parents=True, exist_ok=True)

    def run(shard: str) -> tuple[bool, float]:
        command = ["nox", "-e", f"tests-{args.python}(shard='{shard}')", "--"]
        # Parallel sessions would write the same coverage files, and nothing
        # reads them.
        command.append("--no-cov")
        if shard not in args.unfiltered:
            command += ["-m", "trace_server"]
        url = servers.get()
        started = time.monotonic()
        try:
            with (args.log_dir / f"{shard}.log").open("w") as log:
                for attempt in range(1, args.attempts + 1):
                    print(f"Attempt {attempt} of {args.attempts}", file=log, flush=True)
                    # Its own session, so a timeout also kills pytest under nox.
                    process = subprocess.Popen(
                        command,
                        env={**os.environ, "WF_TRACE_SERVER_URL": url},
                        stdout=log,
                        stderr=subprocess.STDOUT,
                        start_new_session=True,
                    )
                    try:
                        if process.wait(timeout=args.timeout) == 0:
                            return True, time.monotonic() - started
                    except subprocess.TimeoutExpired:
                        os.killpg(process.pid, signal.SIGKILL)
                        process.wait()
                        print(f"Killed after {args.timeout}s", file=log, flush=True)
            return False, time.monotonic() - started
        finally:
            servers.put(url)

    results: dict[str, bool] = {}
    with ThreadPoolExecutor(max_workers=servers.qsize()) as pool:
        futures = {pool.submit(run, shard): shard for shard in args.shards}
        for future in as_completed(futures):
            shard = futures[future]
            passed, seconds = future.result()
            results[shard] = passed
            status = "passed" if passed else "FAILED"
            output = (args.log_dir / f"{shard}.log").read_text(errors="replace")
            print(f"::group::{shard} {status} in {seconds:.0f}s", flush=True)
            print(output, flush=True)
            print("::endgroup::", flush=True)

    failed = [shard for shard in args.shards if not results[shard]]
    for shard in failed:
        print(f"::error::Shard {shard} failed; its log is in the group above")
    print(f"{len(args.shards) - len(failed)} of {len(args.shards)} shards passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
