#!/usr/bin/env python3
from __future__ import annotations

import os
import re
import sys

import requests


def create_failure_comment(message: str) -> None:
    """Create a failure comment on the PR."""
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        print("Error: GITHUB_TOKEN not found")
        sys.exit(1)

    repo = os.environ.get("GITHUB_REPOSITORY")
    pr_number = os.environ.get("PR_NUMBER")

    if not repo or not pr_number:
        print("Error: GITHUB_REPOSITORY or PR_NUMBER not found")
        sys.exit(1)

    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json",
    }

    comment_body = (
        f"❌ Documentation Reference Check Failed\n\n{message}\n\n"
        'This check is required for all PRs that start with "feat(weave)" unless they explicitly state "docs are not required". '
        "Please update your PR description and this check will run again automatically."
    )

    # Post the comment
    url = f"https://api.github.com/repos/{repo}/issues/{pr_number}/comments"
    response = requests.post(url, json={"body": comment_body}, headers=headers)

    if response.status_code != 201:
        print(f"Failed to create comment: {response.status_code}")
        print(response.text)

    print(f"::error::{message}")
    sys.exit(1)


def cleanup_previous_comments() -> None:
    """Delete any previous failure comments from this workflow."""
    token = os.environ.get("GITHUB_TOKEN")
    repo = os.environ.get("GITHUB_REPOSITORY")
    pr_number = os.environ.get("PR_NUMBER")

    if not token or not repo or not pr_number:
        return

    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json",
    }

    # Get all comments on the PR
    url = f"https://api.github.com/repos/{repo}/issues/{pr_number}/comments"
    response = requests.get(url, headers=headers)

    if response.status_code != 200:
        print(f"Failed to get comments: {response.status_code}")
        return

    comments = response.json()

    # Delete previous failure comments
    for comment in comments:
        if comment["body"].startswith("❌ Documentation Reference Check Failed"):
            delete_url = (
                f"https://api.github.com/repos/{repo}/issues/comments/{comment['id']}"
            )
            requests.delete(delete_url, headers=headers)


def validate_docs_pr(pr_number: int) -> bool:
    """Validate that the docs PR exists and is open."""
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        print("Error: GITHUB_TOKEN not found")
        return False

    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json",
    }

    url = f"https://api.github.com/repos/wandb/docs/pulls/{pr_number}"
    response = requests.get(url, headers=headers)

    if response.status_code == 404:
        create_failure_comment(
            f"Documentation PR #{pr_number} not found. Please ensure the PR number is correct."
        )
        return False

    if response.status_code != 200:
        create_failure_comment(f"Error checking docs PR: {response.text}")
        return False

    pr_data = response.json()
    if pr_data["state"] != "open":
        create_failure_comment(
            f"The linked documentation PR #{pr_number} is not open. "
            "Please ensure the documentation PR is open before merging this PR."
        )
        return False

    print(f"✅ Found corresponding docs PR: #{pr_number}")
    return True


def main() -> None:
    """Main function to validate documentation coverage."""
    pr_title = os.environ.get("PR_TITLE", "")
    pr_body = os.environ.get("PR_BODY", "")

    if not pr_title.startswith("feat(weave)"):
        # PR title does not start with "feat(weave)". Skipping documentation check.
        return

    # Check if PR body explicitly states "docs are not required" (case insensitive)
    if re.search(r"docs are not required", pr_body, re.IGNORECASE):
        print('PR body states "docs are not required". Skipping documentation check.')
        return

    # Cleanup any previous comments
    cleanup_previous_comments()

    # Regular expressions to match either:
    # - A link to a docs PR (format: wandb/docs#XXX or https://github.com/wandb/docs/pull/XXX)  # noqa: FIX003
    # - A Jira ticket reference (format: DOCS-XXX or https://wandb.atlassian.net/browse/DOCS-XXX)
    docs_link_regex = r"(?:https://github\.com/wandb/docs/pull/|wandb/docs#)(\d+)"
    jira_link_regex = r"(?:https://wandb\.atlassian\.net/browse/)?DOCS-\d+"

    docs_pr_match = re.search(docs_link_regex, pr_body)
    jira_match = re.search(jira_link_regex, pr_body)

    if not docs_pr_match and not jira_match:
        create_failure_comment(
            "No documentation reference found in the PR description. Please add either:\n"
            "- A link to a docs PR (format: wandb/docs#XXX or https://github.com/wandb/docs/pull/XXX)\n"
            "- A Jira ticket reference (format: DOCS-XXX or https://wandb.atlassian.net/browse/DOCS-XXX)"
        )
        return

    # If we found a docs PR link, validate that it exists and is open
    if docs_pr_match:
        docs_pr_number = int(docs_pr_match.group(1))
        validate_docs_pr(docs_pr_number)

    # If we found a Jira ticket link, we don't need to validate it further
    if jira_match:
        print(f"✅ Found corresponding DOCS Jira ticket: {jira_match.group(0)}")


if __name__ == "__main__":
    main()
