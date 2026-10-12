"""Server-side ingest sampler for the spans (agents) data model.

Drops a deterministic fraction of non-eval traces at OTel ingest -- before
they reach ClickHouse or the scoring Kafka topic -- so operators can enforce
one central sampling rate to cut storage cost. Mirrors the calls-model
sampler in the trace-server service: both read the same
``WEAVE_INGEST_SAMPLE_RATE`` / ``WEAVE_INGEST_SAMPLE_DRY_RUN`` environment
variables and share the same hash, so a trace that writes into both data
models gets one verdict -- when both models record the same ``trace_id``
string. Off by default (rate 1.0). See WB-36877.

The keep/drop decision is a pure hash of ``trace_id``, so every span of a
trace gets the same verdict and a trace is kept or dropped whole. A trace is
always kept when any of its spans in the request carries a ``weave.eval.*``
attribute (best-effort eval carve-out). Spans kept *by the hash* (sampling
enabled, not dry-run) get the applied rate stamped into
``custom_attrs_float["weave.ingest_sample_rate"]`` so downstream consumers
can weight each kept span as ``1/rate`` originals; spans kept whole (evals,
sampler off, dry-run, unusable trace_id) carry no stamp and count as
themselves.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import TYPE_CHECKING, NamedTuple

from weave.trace_server import environment as wf_env
from weave.trace_server.agents import ingest_sampling_metrics as metrics
from weave.trace_server.constants import EVAL_SPAN_ATTR_PREFIX
from weave.trace_server.opentelemetry.helpers import get_attribute

if TYPE_CHECKING:
    from collections.abc import Sequence

    from weave.trace_server.agents.schema import AgentSpanCHInsertable
    from weave.trace_server.opentelemetry.python_spans import Span

# Attribute key the applied sample rate is stamped under on kept spans. The
# flat dotted form is how custom attributes are stored on span rows; the calls
# model records the same fact as ``attributes["weave"]["ingest_sample_rate"]``.
INGEST_SAMPLE_RATE_ATTR = "weave.ingest_sample_rate"

# sha256(trace_id) is reduced modulo this many buckets; a trace is kept when
# its bucket falls below rate * buckets. Must stay byte-identical to the
# calls-model sampler in core (services/weave-trace/src/ingest_sampling.py):
# a trace that writes into both models must get one verdict. There is no shared
# source yet -- if you change this or keep_by_hash, change that copy too
# (cross-repo unification is a tracked follow-up).
_HASH_BUCKETS = 1_000_000

# OTel's spec-invalid trace id: 16 zero bytes -> 32 hex zeros. Kept fail-open
# (see _usable_trace_id) rather than hashed, so it is not a shared drop bucket.
_INVALID_ALL_ZERO_TRACE_ID = "0" * 32


@dataclass(frozen=True)
class SamplingConfig:
    rate: float
    dry_run: bool

    @property
    def enabled(self) -> bool:
        # rate >= 1.0 keeps everything; treat as fully off so the ingest path
        # runs its unmodified single-pass loop and emits no metrics.
        return self.rate < 1.0


def request_config() -> SamplingConfig:
    """Read the sampler config from the environment, once per request."""
    return SamplingConfig(
        rate=wf_env.wf_ingest_sample_rate(),
        dry_run=wf_env.wf_ingest_sample_dry_run(),
    )


def keep_by_hash(trace_id: str, rate: float) -> bool:
    """Deterministic per-trace keep decision; True means keep.

    Pure function of (trace_id, rate), byte-identical to the calls-model
    sampler's formula: one trace_id always lands in one bucket, so every span
    of a trace shares a verdict at a fixed rate.
    """
    bucket = (
        int(hashlib.sha256(trace_id.encode("utf-8")).hexdigest(), 16) % _HASH_BUCKETS
    )
    return bucket < rate * _HASH_BUCKETS


def _usable_trace_id(trace_id: str) -> bool:
    """Whether a trace_id can key the hash.

    OTel requires a 16-byte, not-all-zero trace id. ``Span.from_proto``
    hexlifies whatever bytes arrive, so a malformed id shows up here as a
    wrong-length string and the spec-invalid zero id as 32 zeros. Those are
    sentinels shared across broken clients -- hashing them would hand every
    such client one collective verdict -- so they fail open instead (kept,
    counted as parse failures).
    """
    return len(trace_id) == 32 and trace_id != _INVALID_ALL_ZERO_TRACE_ID


class SpanDecision(NamedTuple):
    """Per-span verdict: whether to drop, and the rate to stamp on a keep.

    ``sampled_rate`` is set only on a genuine hash-keep (sampling enabled, not
    dry-run); every kept-whole path (see module docstring) leaves it None.
    """

    drop: bool
    sampled_rate: float | None = None


def decide_spans(
    config: SamplingConfig,
    spans: Sequence[Span],
    byte_sizes: Sequence[int],
) -> list[SpanDecision]:
    """Decide keep/drop for every parsed span of one export request.

    The verdict is per trace: a trace is kept whole when any of its spans in
    this request carries a ``weave.eval.*`` marker, otherwise the trace hash
    decides. Spans whose trace_id is unusable are kept individually
    (fail-open). ``byte_sizes`` -- serialized protobuf sizes aligned with
    ``spans`` -- feed the dropped-bytes counter. Metrics count spans, not
    traces, and are emitted once per call.
    """
    # Two passes, not one: the verdict is per trace, but a request carries many
    # trace_ids and the eval marker can sit on any span of a trace -- including
    # one that arrives after other spans of the same trace_id. So we must scan
    # every span to learn which trace_ids are evals BEFORE deciding any span; a
    # single loop with a bool cannot keep already-seen spans of a trace whose
    # marker shows up later, nor track multiple trace_ids at once.
    eval_traces: set[str] = set()
    for span in spans:
        if _usable_trace_id(span.trace_id) and get_attribute(
            span.attributes, EVAL_SPAN_ATTR_PREFIX
        ):
            eval_traces.add(span.trace_id)

    # Counters are aggregated and emitted once per request: per-span UDP
    # packets would triple the syscall count on large exports for no gain.
    parse_failure_count = 0
    evals_kept_count = 0
    dropped_count = 0
    dropped_bytes = 0

    decisions: list[SpanDecision] = []
    for span, byte_size in zip(spans, byte_sizes, strict=True):
        trace_id = span.trace_id
        if not _usable_trace_id(trace_id):
            parse_failure_count += 1
            decisions.append(SpanDecision(drop=False))
        elif trace_id in eval_traces:
            evals_kept_count += 1
            decisions.append(SpanDecision(drop=False))
        elif keep_by_hash(trace_id, config.rate):
            # In dry-run nothing is dropped, so the hash winners don't
            # represent 1/rate of the population -- report no rate for them.
            rate = None if config.dry_run else config.rate
            decisions.append(SpanDecision(drop=False, sampled_rate=rate))
        else:
            dropped_count += 1
            dropped_bytes += byte_size
            decisions.append(SpanDecision(drop=not config.dry_run))

    # `seen` counts spans that reached the ladder; spans rejected at parse
    # never get here, so total arrivals = seen + the caller's parse rejects.
    if spans:
        metrics.seen(len(spans))
    if parse_failure_count:
        metrics.parse_failures(parse_failure_count)
    if evals_kept_count:
        metrics.evals_kept(evals_kept_count)
    if dropped_count:
        metrics.dropped(dropped_count, dropped_bytes, config.dry_run)
    return decisions


def stamp_sample_rate(row: AgentSpanCHInsertable, rate: float) -> None:
    """Stamp the applied rate; runs post-extraction, so the per-span attribute
    cap can't evict it and a client-supplied float under the key is overwritten.
    """
    row.custom_attrs_float[INGEST_SAMPLE_RATE_ATTR] = rate
