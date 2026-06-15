"""Mark and close pull requests that have been in draft for too long.

A PR that has been a *draft* for longer than ``--stale-after-days`` is labeled
``stale-draft`` and warned; once it has carried that label for
``--close-after-days`` it is closed. The two-phase mark -> grace -> close flow
guarantees every PR gets a warning window before it is closed.

This is intentionally separate from ``close-inactive-prs.yml`` (which uses
``actions/stale``): that workflow triggers on *inactivity* and cannot filter on
draft state. The signal here is *how long a PR has been a draft*, not how long
since its last update.

Usage:
    As a script:
        $ GITHUB_TOKEN=... uv run scripts/close_stale_draft_prs.py --repo wandb/weave --dry-run

    As a GitHub Action:
        See .github/workflows/close-stale-draft-prs.yml

Environment variables:
    GITHUB_TOKEN (or GH_TOKEN): GitHub API token (required).
    GITHUB_REPOSITORY: "owner/repo"; used when --repo is omitted (set by Actions).
    GITHUB_STEP_SUMMARY: if set, a markdown summary is appended (set by Actions).

Dependencies are declared in the script directive below; ``uv run`` installs them.
"""

# /// script
# dependencies = [
#   "PyGithub>=2.0",
# ]
# ///

from __future__ import annotations

import argparse
import logging
import os
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import TYPE_CHECKING

# PyGithub is needed only for the GitHub I/O layer (declared in the PEP 723 block
# above and installed by `uv run`). Keep it optional so the pure decision logic
# can be imported for unit tests without it.
try:
    from github import Auth, Github, UnknownObjectException
except ImportError:  # pragma: no cover - only when PyGithub is absent
    Auth = Github = UnknownObjectException = None  # type: ignore[assignment,misc]

if TYPE_CHECKING:
    from collections.abc import Iterable

    from github.PullRequest import PullRequest
    from github.Repository import Repository

logger = logging.getLogger("close_stale_draft_prs")

# --- Configuration defaults -----------------------------------------------------
DEFAULT_STALE_AFTER_DAYS = 30  # mark a PR stale once it has been a draft this long
DEFAULT_CLOSE_AFTER_DAYS = 1  # close a stale draft this long after it was marked
DEFAULT_STALE_LABEL = "stale-draft"
DEFAULT_EXEMPT_LABELS: tuple[str, ...] = ("do-not-close",)
STALE_LABEL_COLOR = "ededed"
STALE_LABEL_DESCRIPTION = "Draft PR open for over a month; scheduled for auto-closure"

# Issue-event type names we react to (from the GitHub issue-events API).
EVENT_CONVERT_TO_DRAFT = "convert_to_draft"
EVENT_READY_FOR_REVIEW = "ready_for_review"
EVENT_LABELED = "labeled"

SECONDS_PER_DAY = 86_400
# --------------------------------------------------------------------------------


class Action(Enum):
    """What to do with a single pull request."""

    SKIP = "skip"
    MARK_STALE = "mark_stale"
    CLOSE = "close"


@dataclass(frozen=True, slots=True)
class StaleConfig:
    """Thresholds and labels that govern the sweep."""

    stale_after_days: int = DEFAULT_STALE_AFTER_DAYS
    close_after_days: int = DEFAULT_CLOSE_AFTER_DAYS
    stale_label: str = DEFAULT_STALE_LABEL
    exempt_labels: tuple[str, ...] = DEFAULT_EXEMPT_LABELS


@dataclass(frozen=True, slots=True)
class EventRecord:
    """A minimal, provider-agnostic view of one GitHub issue event."""

    event: str
    created_at: datetime | None
    label_name: str | None = None


@dataclass(frozen=True, slots=True)
class PRSnapshot:
    """Everything the decision logic needs about one pull request."""

    number: int
    is_draft: bool
    labels: tuple[str, ...]
    draft_since: datetime
    stale_labeled_at: datetime | None


@dataclass(frozen=True, slots=True)
class Decision:
    """The chosen action for a PR, plus a human-readable reason."""

    action: Action
    reason: str


# --- Pure logic (no I/O) --------------------------------------------------------


def reduce_events(
    events: Iterable[EventRecord], created_at: datetime, stale_label: str
) -> tuple[datetime, datetime | None]:
    """Collapse a PR's events into (draft_since, stale_labeled_at).

    ``created_at`` alone is wrong for a PR opened normally and later converted to
    draft, so replay the draft transitions. Events are sorted defensively rather
    than trusting the API's order.
    """
    draft_since: datetime | None = created_at  # assume the PR was created as a draft
    stale_labeled_at: datetime | None = None
    ordered = sorted(
        (e for e in events if e.created_at is not None),
        key=lambda e: e.created_at or created_at,
    )
    for event in ordered:
        if event.event == EVENT_CONVERT_TO_DRAFT:
            draft_since = event.created_at
        elif event.event == EVENT_READY_FOR_REVIEW:
            draft_since = None  # became non-draft; a later convert_to_draft resets it
        elif event.event == EVENT_LABELED and event.label_name == stale_label:
            stale_labeled_at = event.created_at
    # The snapshot says the PR is a draft now; if the last transition left it
    # "ready" (a rare race), fall back to created_at.
    return (draft_since if draft_since is not None else created_at, stale_labeled_at)


def _days_between(earlier: datetime, later: datetime) -> float:
    return (later - earlier).total_seconds() / SECONDS_PER_DAY


def _plural_days(count: int) -> str:
    return f"{count} day" if count == 1 else f"{count} days"


def decide(pr: PRSnapshot, cfg: StaleConfig, now: datetime) -> Decision:
    """Decide what to do with one PR. Pure: same inputs -> same Decision."""
    if not pr.is_draft:
        return Decision(Action.SKIP, "not a draft")
    if any(label in cfg.exempt_labels for label in pr.labels):
        return Decision(Action.SKIP, "carries an exempt label")

    if cfg.stale_label in pr.labels:
        # Already marked: close once the grace period has elapsed. A missing label
        # timestamp means it was labeled but we cannot tell when -- treat it as past
        # the grace period so it does not linger forever.
        if pr.stale_labeled_at is None:
            labeled_days = float("inf")
        else:
            labeled_days = _days_between(pr.stale_labeled_at, now)
        if labeled_days >= cfg.close_after_days:
            return Decision(Action.CLOSE, f"stale for {labeled_days:.0f}d")
        return Decision(Action.SKIP, f"within close grace ({labeled_days:.0f}d)")

    draft_days = _days_between(pr.draft_since, now)
    if draft_days >= cfg.stale_after_days:
        return Decision(Action.MARK_STALE, f"in draft for {draft_days:.0f}d")
    return Decision(Action.SKIP, f"in draft only {draft_days:.0f}d")


def stale_comment(cfg: StaleConfig) -> str:
    """Build the comment posted when a PR is first marked stale."""
    escape = "taken out of draft (marked *Ready for review*)"
    if cfg.exempt_labels:
        escape += f" or given the `{cfg.exempt_labels[0]}` label"
    return (
        f"This pull request has been in **draft** for more than "
        f"{_plural_days(cfg.stale_after_days)}, so it has been labeled "
        f"`{cfg.stale_label}`.\n\n"
        f"It will be **closed automatically in {_plural_days(cfg.close_after_days)}** "
        f"unless it is {escape}."
    )


def close_comment(cfg: StaleConfig) -> str:
    """Build the comment posted when a stale draft PR is closed."""
    return (
        f"Closing this pull request: it has been in **draft** for over "
        f"{_plural_days(cfg.stale_after_days)} and was marked `{cfg.stale_label}` "
        f"without being taken out of draft.\n\n"
        f"Reopen it any time you're ready to continue -- nothing here is lost."
    )


# --- GitHub I/O -----------------------------------------------------------------


def _ensure_utc(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)


def _event_records(pr: PullRequest) -> list[EventRecord]:
    records: list[EventRecord] = []
    for event in pr.get_issue_events():
        created = (
            _ensure_utc(event.created_at) if event.created_at is not None else None
        )
        label_name = event.label.name if event.label is not None else None
        records.append(
            EventRecord(event=event.event, created_at=created, label_name=label_name)
        )
    return records


def _snapshot(pr: PullRequest, cfg: StaleConfig) -> PRSnapshot:
    created_at = _ensure_utc(pr.created_at)
    draft_since, stale_labeled_at = reduce_events(
        _event_records(pr), created_at, cfg.stale_label
    )
    return PRSnapshot(
        number=pr.number,
        is_draft=bool(pr.draft),
        labels=tuple(label.name for label in pr.labels),
        draft_since=draft_since,
        stale_labeled_at=stale_labeled_at,
    )


def _ensure_label(repo: Repository, cfg: StaleConfig) -> None:
    try:
        repo.get_label(cfg.stale_label)
    except UnknownObjectException:
        repo.create_label(
            name=cfg.stale_label,
            color=STALE_LABEL_COLOR,
            description=STALE_LABEL_DESCRIPTION,
        )
        logger.info("Created label %r", cfg.stale_label)


def _apply(
    decision: Decision, pr: PullRequest, repo: Repository, cfg: StaleConfig
) -> None:
    if decision.action is Action.SKIP:
        return
    if decision.action is Action.MARK_STALE:
        _ensure_label(repo, cfg)
        pr.add_to_labels(cfg.stale_label)
        pr.create_issue_comment(stale_comment(cfg))
        return
    if decision.action is Action.CLOSE:
        pr.create_issue_comment(close_comment(cfg))
        pr.edit(state="closed")
        return
    raise AssertionError(f"unhandled action: {decision.action!r}")


def _process_pr(
    pr: PullRequest, repo: Repository, cfg: StaleConfig, now: datetime, *, dry_run: bool
) -> Decision:
    # Cheap rejects that avoid the per-PR events API call. `decide` re-validates
    # all of these, so this block is an optimization, not the source of truth.
    if not pr.draft:
        return Decision(Action.SKIP, "not a draft")
    labels = tuple(label.name for label in pr.labels)
    if any(label in cfg.exempt_labels for label in labels):
        return Decision(Action.SKIP, "carries an exempt label")
    has_stale = cfg.stale_label in labels
    created_age = _days_between(_ensure_utc(pr.created_at), now)
    if not has_stale and created_age < cfg.stale_after_days:
        # created_at is an upper bound on draft age, so it cannot be stale yet.
        return Decision(Action.SKIP, f"in draft only {created_age:.0f}d")

    decision = decide(_snapshot(pr, cfg), cfg, now)
    if not dry_run:
        _apply(decision, pr, repo, cfg)
    return decision


def run(
    repo_full_name: str, cfg: StaleConfig, now: datetime, *, token: str, dry_run: bool
) -> list[tuple[int, Decision]]:
    """Sweep all open PRs in a repo and return (number, decision) per PR."""
    if Github is None or Auth is None:
        raise RuntimeError("PyGithub is required; install it or run via `uv run`.")
    repo = Github(auth=Auth.Token(token)).get_repo(repo_full_name)
    results: list[tuple[int, Decision]] = []
    for pr in repo.get_pulls(state="open"):
        try:
            decision = _process_pr(pr, repo, cfg, now, dry_run=dry_run)
        except Exception as exc:  # one bad PR must not abort the whole sweep
            logger.warning("Skipping #%s: %s", pr.number, exc)
            continue
        results.append((pr.number, decision))
        if decision.action is not Action.SKIP:
            logger.info(
                "%s#%s -> %s (%s)",
                "[dry-run] " if dry_run else "",
                pr.number,
                decision.action.value,
                decision.reason,
            )
    return results


def _write_step_summary(results: list[tuple[int, Decision]], *, dry_run: bool) -> None:
    path = os.environ.get("GITHUB_STEP_SUMMARY")
    if not path:
        return
    acted = [(n, d) for n, d in results if d.action is not Action.SKIP]
    lines = ["# Stale draft PR sweep", ""]
    if dry_run:
        lines.append("_Dry run -- no changes were made._")
        lines.append("")
    if acted:
        lines.extend(f"- #{n}: {d.action.value} ({d.reason})" for n, d in acted)
    else:
        lines.append("- No draft PRs were marked or closed.")
    with open(path, "a", encoding="utf-8") as handle:
        handle.write("\n".join(lines) + "\n")


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Mark and close stale draft PRs.")
    parser.add_argument(
        "--repo",
        default=os.environ.get("GITHUB_REPOSITORY"),
        help="owner/repo (default: $GITHUB_REPOSITORY)",
    )
    parser.add_argument(
        "--stale-after-days", type=int, default=DEFAULT_STALE_AFTER_DAYS
    )
    parser.add_argument(
        "--close-after-days", type=int, default=DEFAULT_CLOSE_AFTER_DAYS
    )
    parser.add_argument("--stale-label", default=DEFAULT_STALE_LABEL)
    parser.add_argument(
        "--exempt-label",
        action="append",
        dest="exempt_labels",
        help=f"repeatable; defaults to {list(DEFAULT_EXEMPT_LABELS)}",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="log decisions without changing anything",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point. Returns a process exit code."""
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    args = _parse_args(argv)
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if not token:
        logger.error("GITHUB_TOKEN (or GH_TOKEN) must be set.")
        return 2
    if not args.repo:
        logger.error("--repo or GITHUB_REPOSITORY must be set.")
        return 2

    cfg = StaleConfig(
        stale_after_days=args.stale_after_days,
        close_after_days=args.close_after_days,
        stale_label=args.stale_label,
        exempt_labels=tuple(args.exempt_labels)
        if args.exempt_labels
        else DEFAULT_EXEMPT_LABELS,
    )
    now = datetime.now(timezone.utc)
    results = run(args.repo, cfg, now, token=token, dry_run=args.dry_run)

    marked = sum(1 for _, d in results if d.action is Action.MARK_STALE)
    closed = sum(1 for _, d in results if d.action is Action.CLOSE)
    _write_step_summary(results, dry_run=args.dry_run)
    logger.info(
        "%sDone. Scanned %d open PR(s); marked %d, closed %d.",
        "[dry-run] " if args.dry_run else "",
        len(results),
        marked,
        closed,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
