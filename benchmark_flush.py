"""Benchmark comparing Python vs Go sender flush performance.

This benchmark measures the time from creating N calls until all data
has been flushed to the server.

Usage:
    # Python implementation (default)
    python benchmark_flush.py

    # Go sidecar implementation
    WEAVE_USE_GO_SENDER=true python benchmark_flush.py

    # Go sidecar with custom socket (for snooping)
    WEAVE_USE_GO_SENDER=true WEAVE_GO_SENDER_SOCKET_PATH=/tmp/my-weave.sock python benchmark_flush.py
"""

from __future__ import annotations

import os
import time

import weave
from weave.trace_server_bindings.go_sender_trace_server import GoSenderTraceServer


@weave.op
def dummy_op(x: int) -> dict:
    """A simple op that returns some data."""
    return {"value": x, "squared": x * x, "message": f"processed {x}"}


def run_benchmark(num_calls: int = 1000) -> dict:
    """Run the benchmark and return timing results."""
    use_go = os.environ.get("WEAVE_USE_GO_SENDER", "").lower() in ("true", "1", "yes")
    impl_name = "Go sidecar" if use_go else "Python"

    print(f"\n{'='*60}")
    print(f"Benchmark: {impl_name} implementation")
    print(f"Number of calls: {num_calls}")
    print(f"{'='*60}\n")

    # Initialize weave
    client = weave.init("benchmark-flush-test")

    # Warm up - make one call first
    print("Warming up...")
    dummy_op(0)
    client.flush()

    # For Go sender, also wait for actual completion
    if use_go and hasattr(client, 'server') and isinstance(client.server, GoSenderTraceServer):
        client.server.wait_idle()

    time.sleep(0.5)

    # Start timing
    print(f"Starting {num_calls} calls...")
    start_time = time.perf_counter()

    # Make all the calls
    call_start_time = time.perf_counter()
    for i in range(1, num_calls + 1):
        dummy_op(i)
    call_end_time = time.perf_counter()
    call_duration = call_end_time - call_start_time

    print(f"All calls initiated in {call_duration:.3f}s")
    print(f"  Rate: {num_calls / call_duration:.1f} calls/sec")

    # Flush and measure
    print("Flushing...")
    flush_start_time = time.perf_counter()

    if use_go and hasattr(client, 'server') and isinstance(client.server, GoSenderTraceServer):
        # For Go sender, we bypass future_executor, so just wait for Go sidecar
        print("Waiting for Go sender queue to empty...")
        stats_before = client.server.stats()
        print(f"  Stats before wait_queue_empty: {stats_before}")
        client.server.wait_queue_empty()
        stats_after = client.server.stats()
        print(f"  Stats after wait_queue_empty: {stats_after}")
    else:
        # For Python sender, flush the future_executor
        client.flush()

    flush_end_time = time.perf_counter()
    flush_duration = flush_end_time - flush_start_time

    # Total time
    total_duration = flush_end_time - start_time

    print(f"\nResults:")
    print(f"  Call creation time: {call_duration:.3f}s")
    print(f"  Flush time:         {flush_duration:.3f}s")
    print(f"  Total time:         {total_duration:.3f}s")
    print(f"  Throughput:         {num_calls / total_duration:.1f} calls/sec (end-to-end)")

    return {
        "implementation": impl_name,
        "num_calls": num_calls,
        "call_duration": call_duration,
        "flush_duration": flush_duration,
        "total_duration": total_duration,
        "throughput": num_calls / total_duration,
    }


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Benchmark weave flush performance")
    parser.add_argument(
        "-n", "--num-calls",
        type=int,
        default=1000,
        help="Number of calls to make (default: 1000)"
    )
    args = parser.parse_args()

    results = run_benchmark(num_calls=args.num_calls)

    print(f"\n{'='*60}")
    print("Summary:")
    print(f"  {results['implementation']}: {results['total_duration']:.3f}s total")
    print(f"  ({results['throughput']:.1f} calls/sec)")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
