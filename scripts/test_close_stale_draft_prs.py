"""Unit tests for the pure decision logic in close_stale_draft_prs.

These drive the public functions with plain data -- no GitHub, no mocking.
Run: uv run --with pytest pytest scripts/test_close_stale_draft_prs.py
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from close_stale_draft_prs import (
    Action,
    EventRecord,
    PRSnapshot,
    StaleConfig,
    decide,
    reduce_events,
    stale_comment,
)

CFG = StaleConfig()
NOW = datetime(2026, 6, 13, tzinfo=timezone.utc)


def _ago(days: float) -> datetime:
    return NOW - timedelta(days=days)


def _snap(
    *,
    is_draft: bool = True,
    labels: tuple[str, ...] = (),
    draft_since: datetime | None = None,
    stale_labeled_at: datetime | None = None,
) -> PRSnapshot:
    return PRSnapshot(
        number=1,
        is_draft=is_draft,
        labels=labels,
        draft_since=draft_since if draft_since is not None else _ago(0),
        stale_labeled_at=stale_labeled_at,
    )


# --- reduce_events --------------------------------------------------------------


def test_reduce_events_created_as_draft_uses_created_at() -> None:
    created = _ago(40)
    draft_since, stale_at = reduce_events([], created, CFG.stale_label)
    assert draft_since == created
    assert stale_at is None


def test_reduce_events_uses_latest_convert_to_draft() -> None:
    events = [
        EventRecord("ready_for_review", _ago(20)),
        EventRecord("convert_to_draft", _ago(5)),
    ]
    draft_since, _ = reduce_events(events, _ago(40), CFG.stale_label)
    assert draft_since == _ago(5)


def test_reduce_events_ready_after_draft_falls_back_to_created_at() -> None:
    created = _ago(40)
    events = [
        EventRecord("convert_to_draft", _ago(10)),
        EventRecord("ready_for_review", _ago(2)),
    ]
    draft_since, _ = reduce_events(events, created, CFG.stale_label)
    assert draft_since == created


def test_reduce_events_picks_latest_stale_label_time() -> None:
    events = [
        EventRecord("labeled", _ago(8), label_name="some-other-label"),
        EventRecord("labeled", _ago(6), label_name=CFG.stale_label),
    ]
    _, stale_at = reduce_events(events, _ago(40), CFG.stale_label)
    assert stale_at == _ago(6)


def test_reduce_events_sorts_unordered_input() -> None:
    events = [
        EventRecord("convert_to_draft", _ago(5)),
        EventRecord("ready_for_review", _ago(20)),
    ]
    draft_since, _ = reduce_events(events, _ago(40), CFG.stale_label)
    assert draft_since == _ago(5)  # convert (5d ago) is newer than ready (20d ago)


# --- decide ---------------------------------------------------------------------


def test_decide_marks_old_draft() -> None:
    assert decide(_snap(draft_since=_ago(31)), CFG, NOW).action is Action.MARK_STALE


def test_decide_skips_young_draft() -> None:
    assert decide(_snap(draft_since=_ago(10)), CFG, NOW).action is Action.SKIP


def test_decide_skips_non_draft() -> None:
    snap = _snap(is_draft=False, draft_since=_ago(99))
    assert decide(snap, CFG, NOW).action is Action.SKIP


def test_decide_skips_exempt_label() -> None:
    snap = _snap(draft_since=_ago(99), labels=("do-not-close",))
    assert decide(snap, CFG, NOW).action is Action.SKIP


def test_decide_closes_after_grace() -> None:
    cfg = StaleConfig(close_after_days=3)
    snap = _snap(labels=(cfg.stale_label,), stale_labeled_at=_ago(5))
    assert decide(snap, cfg, NOW).action is Action.CLOSE


def test_decide_skips_within_grace() -> None:
    cfg = StaleConfig(close_after_days=3)
    snap = _snap(labels=(cfg.stale_label,), stale_labeled_at=_ago(1))
    assert decide(snap, cfg, NOW).action is Action.SKIP


def test_decide_default_grace_closes_one_day_after_marking() -> None:
    # The default grace is 1 day: a PR marked ~25h ago should close.
    snap = _snap(labels=(CFG.stale_label,), stale_labeled_at=_ago(1.05))
    assert decide(snap, CFG, NOW).action is Action.CLOSE


def test_decide_default_grace_skips_under_one_day() -> None:
    snap = _snap(labels=(CFG.stale_label,), stale_labeled_at=_ago(0.5))
    assert decide(snap, CFG, NOW).action is Action.SKIP


def test_decide_closes_stale_label_without_timestamp() -> None:
    snap = _snap(labels=(CFG.stale_label,), stale_labeled_at=None)
    assert decide(snap, CFG, NOW).action is Action.CLOSE


def test_decide_exempt_label_beats_stale_label() -> None:
    snap = _snap(labels=(CFG.stale_label, "do-not-close"), stale_labeled_at=_ago(99))
    assert decide(snap, CFG, NOW).action is Action.SKIP


def test_stale_comment_pluralizes_single_day() -> None:
    text = stale_comment(StaleConfig(close_after_days=1))
    assert "closed automatically in 1 day" in text
    assert "1 days" not in text


def test_stale_comment_pluralizes_multiple_days() -> None:
    assert "closed automatically in 7 days" in stale_comment(
        StaleConfig(close_after_days=7)
    )
