"""Test paired core revision selection without GitHub writes or credentials."""

import pytest
from resolve_core_ref import core_commit, paired_core_pr

SHA = "a" * 40


def test_unpaired_change_uses_default() -> None:
    assert paired_core_pr([], "feature", SHA) is None
    assert (
        paired_core_pr([{"head": {"ref": "feature"}, "body": None}], "feature", SHA)
        is None
    )


def test_selects_matching_branch() -> None:
    prs = [
        {
            "head": {"ref": "parent"},
            "body": "Core counterpart: https://github.com/wandb/core/pull/1",
        },
        {
            "head": {"ref": "feature"},
            "body": "Core counterpart: https://github.com/wandb/core/pull/2.",
        },
    ]
    assert paired_core_pr(prs, "feature", SHA) == 2


def test_selects_merged_commit() -> None:
    pr = {
        "head": {"ref": "feature"},
        "merge_commit_sha": SHA,
        "body": "Core counterpart: https://github.com/wandb/core/pull/2",
    }
    assert paired_core_pr([pr], "master", SHA) == 2


@pytest.mark.parametrize(
    "body",
    [
        "Core counterpart: https://github.com/other/repo/pull/2",
        "Core counterpart: https://github.com/wandb/core/pull/not-a-number",
        "Core counterpart: https://github.com/wandb/core/pull/2\nCore counterpart: https://github.com/wandb/core/pull/3",
    ],
)
def test_rejects_malformed_or_duplicate_pair(body: str) -> None:
    with pytest.raises(ValueError, match="Expected one Core counterpart"):
        paired_core_pr([{"head": {"ref": "feature"}, "body": body}], "feature", SHA)


def test_rejects_conflicting_pairs() -> None:
    prs = [
        {
            "head": {"ref": "feature"},
            "body": f"Core counterpart: https://github.com/wandb/core/pull/{number}",
        }
        for number in [2, 3]
    ]
    with pytest.raises(ValueError, match="conflicting"):
        paired_core_pr(prs, "feature", SHA)


def test_pins_first_party_core_commit() -> None:
    assert (
        core_commit({"head": {"repo": {"full_name": "wandb/core"}, "sha": SHA}}) == SHA
    )


@pytest.mark.parametrize("repo", [{"full_name": "someone/core"}, None])
def test_rejects_fork_and_deleted_repository(repo: dict[str, str] | None) -> None:
    with pytest.raises(ValueError, match="wandb/core"):
        core_commit({"head": {"repo": repo, "sha": SHA}})


def test_rejects_non_commit_ref() -> None:
    with pytest.raises(ValueError, match="full commit SHA"):
        core_commit({"head": {"repo": {"full_name": "wandb/core"}, "sha": "master"}})
