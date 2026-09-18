"""Select the explicitly paired core PR for cross-repository tests."""

import json
import os
import re
import subprocess
from pathlib import Path
from typing import Any

PAIR_PATTERN = re.compile(
    r"Core counterpart:\s+https://github\.com/wandb/core/pull/([1-9][0-9]*)\b"
)


def paired_core_pr(
    pull_requests: list[dict[str, Any]], ref_name: str, sha: str
) -> int | None:
    pairs = set()
    for pr in pull_requests:
        if pr["head"]["ref"] != ref_name and pr.get("merge_commit_sha") != sha:
            continue
        body = pr.get("body") or ""
        matches = PAIR_PATTERN.findall(body)
        if "Core counterpart:" in body and len(matches) != 1:
            raise ValueError("Expected one Core counterpart URL in the Weave PR body")
        pairs.update(int(match) for match in matches)
    if len(pairs) > 1:
        raise ValueError("Associated Weave PRs name conflicting core counterparts")
    return next(iter(pairs)) if pairs else None


def core_commit(pull_request: dict[str, Any]) -> str:
    head = pull_request["head"]
    repo = head.get("repo")
    if not repo or repo.get("full_name") != "wandb/core":
        raise ValueError("The paired core PR must use a branch in wandb/core")
    sha = head["sha"]
    if not re.fullmatch(r"[0-9a-f]{40}", sha):
        raise ValueError("The paired core PR must resolve to a full commit SHA")
    return sha


def github_json(endpoint: str, token: str) -> Any:
    return json.loads(
        subprocess.check_output(
            ["gh", "api", endpoint],
            env={**os.environ, "GH_TOKEN": token},
            text=True,
        )
    )


def main() -> None:
    repo = os.environ["GITHUB_REPOSITORY"]
    sha = os.environ["GITHUB_SHA"]
    requests = github_json(f"repos/{repo}/commits/{sha}/pulls", os.environ["GH_TOKEN"])
    pair = paired_core_pr(requests, os.environ["GITHUB_REF_NAME"], sha)
    ref = "master"
    if pair is not None:
        ref = core_commit(
            github_json(f"repos/wandb/core/pulls/{pair}", os.environ["CORE_GH_TOKEN"])
        )
    with Path(os.environ["GITHUB_OUTPUT"]).open("a", encoding="utf-8") as output:
        output.write(f"ref={ref}\n")


if __name__ == "__main__":
    main()
