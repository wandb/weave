"""Server-side ingest sampler for the spans (agents) data model.

Drops a deterministic fraction of non-eval traces at OTel ingest -- before
they reach ClickHouse or the scoring Kafka topic -- so operators can enforce
one central sampling rate to cut storage cost. Mirrors the calls-model
sampler in the trace-server service: both read the same
``WEAVE_INGEST_SAMPLE_RATE`` / ``WEAVE_INGEST_SAMPLE_DRY_RUN`` environment
variables and share the same hash, so a trace that writes into both data
models gets one verdict. Off by default (rate 1.0). See WB-36877.

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
from weave.trace_server.opentelemetry.helpers import get_attribute

if TYPE_CHECKING:
    from collections.abc import Sequence

    from weave.trace_server.agents.schema import AgentSpanCHInsertable
    from weave.trace_server.opentelemetry.python_spans import Span

# Attribute key the applied sample rate is stamped under on kept spans. The
# flat dotted form is how custom attributes are stored on span rows; the calls
# model records the same fact as ``attributes["weave"]["ingest_sample_rate"]``.
INGEST_SAMPLE_RATE_ATTR = "weave.ingest_sample_rate"

# Any non-empty value under this subtree marks a span as belonging to an
# evaluation. The SDK stamps ``weave.eval.predict_and_score_call_id`` etc. on
# every span started inside an eval context -- see the ``EVAL_*_SPAN_ATTR``
# constants in ``weave/trace_server/constants.py``.
_EVAL_MARKER_KEY = "weave.eval"

# sha256(trace_id) is reduced modulo this many buckets; a trace is kept when
# its bucket falls below rate * buckets. Must stay byte-identical to the
# calls-model sampler so a mixed trace gets one verdict across both models.
_HASH_BUCKETS = 1_000_000

_ZERO_TRACE_ID = "0" * 32


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
    return len(trace_id) == 32 and trace_id != _ZERO_TRACE_ID


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
    this request carries the eval marker, otherwise the trace hash decides.
    Spans whose trace_id is unusable are kept individually (fail-open).
    ``byte_sizes`` -- serialized protobuf sizes aligned with ``spans`` -- feed
    the dropped-bytes counter. Metrics count spans, not traces.
    """
    eval_traces: set[str] = set()
    for span in spans:
        if _usable_trace_id(span.trace_id) and get_attribute(
            span.attributes, _EVAL_MARKER_KEY
        ):
            eval_traces.add(span.trace_id)

    decisions: list[SpanDecision] = []
    for span, byte_size in zip(spans, byte_sizes, strict=True):
        metrics.seen(1)
        trace_id = span.trace_id
        if not _usable_trace_id(trace_id):
            metrics.parse_failures(1)
            decisions.append(SpanDecision(drop=False))
        elif trace_id in eval_traces:
            metrics.evals_kept(1)
            decisions.append(SpanDecision(drop=False))
        elif keep_by_hash(trace_id, config.rate):
            # In dry-run nothing is dropped, so the hash winners don't
            # represent 1/rate of the population -- report no rate for them.
            rate = None if config.dry_run else config.rate
            decisions.append(SpanDecision(drop=False, sampled_rate=rate))
        else:
            metrics.dropped(1, byte_size, config.dry_run)
            decisions.append(SpanDecision(drop=not config.dry_run))
    return decisions


def stamp_sample_rate(row: AgentSpanCHInsertable, rate: float) -> None:
    """Record the applied rate on a hash-kept span row.

    Runs after custom-attribute extraction, so the stamp cannot be evicted by
    the per-span attribute cap, and overwrites any client-supplied float under
    the same key.
    """
    row.custom_attrs_float[INGEST_SAMPLE_RATE_ATTR] = rate
