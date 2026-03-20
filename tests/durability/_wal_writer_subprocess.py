"""Helper script for cross-process WAL tests.

Runs in a subprocess to exercise the WAL writer independently from
the sender (which runs in the test process).  Communicates with the
parent via stdin/stdout signals.

Usage (from the test process)::

    proc = subprocess.Popen(
        [sys.executable, "-m", "tests.durability._wal_writer_subprocess",
         wal_dir, str(record_count)],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
    )

Modes:

    **normal** (default): writes records, signals "written", waits for
    parent to send a line on stdin, closes the writer, signals "closed".

    **crash**: pass ``--crash`` as a third argument.  Writes records then
    exits WITHOUT calling ``writer.close()``, leaving a stale .lock file.
"""
from __future__ import annotations

import sys

from weave.durability.wal_directory_manager import FileWALDirectoryManager
from weave.durability.wal_writer import JSONLWALWriter


def main() -> None:
    wal_dir = sys.argv[1]
    count = int(sys.argv[2])
    crash = len(sys.argv) > 3 and sys.argv[3] == "--crash"

    mgr = FileWALDirectoryManager(wal_dir)
    writer = JSONLWALWriter(mgr)
    for i in range(count):
        writer.write({"type": "obj_create", "seq": i})

    if crash:
        # EXIT WITHOUT writer.close() — simulates a crash.
        # The .lock file contains our PID, but we're about to die.
        return

    # Signal that writes are done (writer still open).
    sys.stdout.write("written\n")
    sys.stdout.flush()

    # Wait for the parent to tell us to close.
    sys.stdin.readline()
    writer.close()

    # Signal that close is done.
    sys.stdout.write("closed\n")
    sys.stdout.flush()


if __name__ == "__main__":
    main()
