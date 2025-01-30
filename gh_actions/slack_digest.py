"""
Slack digest tool for GitHub activity reporting.
Run locally with: `uv run gh_actions/slack_digest.py`
Or use as a GitHub Action.
"""

# /// script
# dependencies = [
#   "slack-sdk>=3.0.0",
#   "PyGithub",
#   "rich",
#   "python-dateutil",
#   "pytz",
# ]
# ///

from __future__ import annotations

import argparse
import logging
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

import pytz
import urllib3
from github import Github, GithubException, RateLimitExceededException
from rich.console import Console
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
)
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
console = Console()

# Define a set of distinct colors for users
COLORS = [
    "bright_red",
    "bright_green",
    "bright_yellow",
    "bright_blue",
    "bright_magenta",
    "bright_cyan",
    "orange3",
    "purple",
    "turquoise2",
    "deep_pink2",
    "spring_green1",
    "dark_orange",
    "deep_sky_blue1",
]


@dataclass
class ChangeCategories:
    """Tracks which categories of files were modified."""

    docs: bool = False  # Changes in ./docs
    server: bool = False  # Changes in ./weave/trace_server
    ts_sdk: bool = False  # Changes in ./sdks/node
    tests: bool = False  # Changes in test files
    ui: bool = (
        False  # Changes in weave-js/src/components/PagePanelComponents/Home/Browse3
    )
    py_sdk: bool = False  # Changes in ./weave (excluding trace_server)


@dataclass
class CategoryInfo:
    """Information about a category of changes."""

    emoji: str
    name: str
    path: str


# Define categories with their emojis and paths
CATEGORIES = {
    "docs": CategoryInfo("📚", "Docs", "./docs"),
    "tests": CategoryInfo("🧪", "Tests", "test"),
    "server": CategoryInfo("🤖", "Server", "./weave/trace_server"),
    "ui": CategoryInfo(
        "🎨", "UI", "weave-js/src/components/PagePanelComponents/Home/Browse3"
    ),
    "ts_sdk": CategoryInfo("📦", "TS SDK", "./sdks/node"),
    "py_sdk": CategoryInfo("🐍", "Python SDK", "./weave"),
}


class SlackNotifier:
    def __init__(self, token: str):
        """Initialize Slack notifier with authentication token.

        Args:
            token: Slack API token for authentication
        """
        self.client = WebClient(token=token)

    def validate_channel(self, channel: str) -> str:
        """Validate and format Slack channel name.

        Args:
            channel: Channel name with or without '#' prefix

        Returns:
            Properly formatted channel name

        Raises:
            ValueError: If channel name is invalid
        """
        if not channel:
            raise ValueError("Channel name cannot be empty")

        # Ensure channel starts with #
        return f"#{channel.lstrip('#')}"

    def send_message(self, channel: str, message: str) -> bool:
        """Send message to specified Slack channel.

        Args:
            channel: Target Slack channel
            message: Message content to send

        Returns:
            bool: True if message was sent successfully

        Raises:
            SlackApiError: If message sending fails
        """
        try:
            channel = self.validate_channel(channel)
            response = self.client.chat_postMessage(channel=channel, text=message)
            logger.info(f"Message sent successfully to {channel}")
        except SlackApiError as e:
            logger.exception(f"Failed to send message: {e.response['error']}")
            raise
        return True


class GitHubDigest:
    """Handles GitHub repository activity reporting."""

    def __init__(
        self,
        token: str,
        repo: str,
        days: int = 7,
        branch: str = "master",
        local_mode: bool = True,
    ):
        """Initialize GitHub digest generator."""
        # Configure connection pool for parallel requests
        self.pool_manager = urllib3.PoolManager(maxsize=32)
        self.github = Github(token, pool_size=32, retry=3)
        self.repo = self.github.get_repo(repo)
        self.days = days
        self.branch = branch
        self.local_mode = local_mode
        self.progress = None
        self._last_rate_check = 0
        self._rate_limit_remaining = None

    def _get_progress(self) -> Progress | None:
        """Get progress indicator if in local mode."""
        if not self.local_mode:
            return None

        if not self.progress:
            self.progress = Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TaskProgressColumn(),
                console=console,
            )
        return self.progress

    def _should_check_rate_limit(self) -> bool:
        """Determine if we should check rate limit again."""
        now = time.time()
        # Only check rate limit every 60 seconds unless we know we're low
        if self._rate_limit_remaining is None or self._rate_limit_remaining < 100:
            # Check more frequently if we're running low
            return (now - self._last_rate_check) > 5
        return (now - self._last_rate_check) > 60

    def _handle_rate_limit(self):
        """Handle GitHub API rate limit by waiting if needed."""
        if not self._should_check_rate_limit():
            return

        self._last_rate_check = time.time()
        rate_limit = self.github.get_rate_limit()
        self._rate_limit_remaining = rate_limit.core.remaining

        if rate_limit.core.remaining == 0:
            reset_timestamp = rate_limit.core.reset.timestamp()
            sleep_time = reset_timestamp - time.time() + 1  # Add 1 second buffer
            if sleep_time > 0:
                logger.warning(
                    f"Rate limit reached. Waiting {sleep_time:.1f} seconds..."
                )
                time.sleep(sleep_time)
                self._rate_limit_remaining = None  # Force a recheck after waiting

    def analyze_paths(self, files) -> ChangeCategories:
        """Analyze file paths to determine which categories were modified."""
        cats = ChangeCategories()
        paths = {f.filename for f in files}

        for path in paths:
            if path.startswith("docs/"):
                cats.docs = True
            elif path.startswith("weave/trace_server/"):
                cats.server = True
            elif path.startswith("sdks/node/"):
                cats.ts_sdk = True
            elif "test" in path:
                cats.tests = True
            elif path.startswith(
                "weave-js/src/components/PagePanelComponents/Home/Browse3/"
            ):
                cats.ui = True
            elif path.startswith("weave/") and not path.startswith(
                "weave/trace_server/"
            ):
                cats.py_sdk = True

        return cats

    def format_line_diff(self, additions: int, deletions: int) -> str:
        """Format the line differences in a compact way."""
        return f"+{additions}/-{deletions}"

    def process_items_parallel(
        self, items: list[Any], processor, description: str
    ) -> list[tuple[Any, Exception | None]]:
        """Process items in parallel using a thread pool."""
        results: list[tuple[Any, Exception | None]] = []
        cpu_count = os.cpu_count()
        max_workers = min(32, (cpu_count or 1) * 4)

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {}

            # Submit all items at once, only checking rate limit periodically
            for item in items:
                try:
                    if len(futures) % 10 == 0:  # Check rate limit every 10 items
                        self._handle_rate_limit()
                    futures[executor.submit(processor, item)] = item
                except GithubException as e:
                    logger.exception(f"GitHub API error while submitting item: {e}")
                    results.append((item, e))

            progress = self._get_progress()
            if progress is not None:
                task = progress.add_task(description, total=len(items))

            for future in as_completed(futures):
                try:
                    result = future.result()
                    results.append((result, None))
                except RateLimitExceededException:
                    original_item = futures[future]
                    try:
                        self._handle_rate_limit()
                        # Retry the item
                        result = processor(original_item)
                        results.append((result, None))
                    except Exception as e:
                        results.append((original_item, e))
                        logger.exception(
                            f"Error processing item after rate limit retry: {e}"
                        )
                except GithubException as e:
                    original_item = futures[future]
                    results.append((original_item, e))
                    logger.exception(f"GitHub API error: {e}")
                except Exception as e:
                    original_item = futures[future]
                    results.append((original_item, e))
                    logger.exception(f"Unexpected error: {e}")

                if progress is not None:
                    progress.update(task, advance=1)

        return results

    def process_commit(self, commit):
        """Process a single commit into row data."""
        date = commit.commit.author.date.strftime("%Y-%m-%d %H:%M")
        author = commit.author.login if commit.author else "Unknown"
        message = commit.commit.message.split("\n")[0]
        stats = commit.stats
        categories = self.analyze_paths(commit.files)

        return {
            "date": date,
            "author": author,
            "message": message,
            "line_diff": self.format_line_diff(stats.additions, stats.deletions),
            "files": str(stats.total),
            "categories": categories,
            "url": commit.html_url,
        }

    def process_pr(self, pr):
        """Process a single PR into row data."""
        date = pr.updated_at.strftime("%Y-%m-%d %H:%M")
        author = pr.user.login
        categories = self.analyze_paths(pr.get_files())

        return {
            "date": date,
            "author": author,
            "title": pr.title,
            "line_diff": self.format_line_diff(pr.additions, pr.deletions),
            "files": str(pr.changed_files),
            "categories": categories,
            "url": pr.html_url,
            "draft": pr.draft,
        }

    def create_commit_table(self, commits, title: str) -> str:
        """Create an ASCII table for displaying commit information."""
        # Process commits in parallel
        results = self.process_items_parallel(
            commits, self.process_commit, "Processing commits..."
        )

        # Format as ASCII table
        table = [title, ""]  # Title and blank line

        # Headers
        headers = ["Date", "Author", "Message", "Line Diff", "Files", "Categories", "Link"]
        # Create header separator
        widths = [12, 15, 50, 12, 6, 12, 50]  # Adjust these as needed
        row_format = "| " + " | ".join(f"{{:<{w}}}" for w in widths) + " |"

        table.append(row_format.format(*headers))
        table.append("|" + "|".join("-" * (w + 2) for w in widths) + "|")

        # Data rows
        for processed, error in results:
            if error is not None:
                logger.warning(f"Skipping commit due to error: {error}")
                continue

            categories = processed["categories"]
            indicators = []
            if categories.docs:   indicators.append("📚")
            if categories.server: indicators.append("🤖")
            if categories.ts_sdk: indicators.append("📦")
            if categories.tests:  indicators.append("🧪")
            if categories.ui:     indicators.append("🎨")
            if categories.py_sdk: indicators.append("🐍")

            cat_str = " ".join(indicators) if indicators else ""

            row = [
                processed["date"],
                processed["author"],
                processed["message"][:47] + "..." if len(processed["message"]) > 50 else processed["message"],
                processed["line_diff"],
                processed["files"],
                cat_str,
                processed["url"],
            ]
            table.append(row_format.format(*row))

        return "\n".join(table)

    def create_pr_tables(self, prs, title_prefix: str) -> tuple[str, str]:
        """Create ASCII tables for pull requests."""
        # Process PRs in parallel
        results = self.process_items_parallel(
            sorted(prs, key=lambda x: x.updated_at, reverse=True),
            self.process_pr,
            "Processing pull requests..."
        )

        # Headers
        headers = ["Date", "Author", "Title", "Line Diff", "Files", "Categories", "Link"]
        widths = [12, 15, 50, 12, 6, 12, 50]  # Adjust these as needed
        row_format = "| " + " | ".join(f"{{:<{w}}}" for w in widths) + " |"

        # Create header rows
        header_row = row_format.format(*headers)
        separator = "|" + "|".join("-" * (w + 2) for w in widths) + "|"

        # Prepare tables
        ready_rows = [
            f"{title_prefix} - Ready for Review",
            "",
            header_row,
            separator
        ]
        draft_rows = [
            f"{title_prefix} - In Progress",
            "",
            header_row,
            separator
        ]

        # Process results
        for processed, error in results:
            if error is not None:
                logger.warning(f"Skipping PR due to error: {error}")
                continue

            categories = processed["categories"]
            indicators = []
            if categories.docs:   indicators.append("📚")
            if categories.server: indicators.append("🤖")
            if categories.ts_sdk: indicators.append("📦")
            if categories.tests:  indicators.append("🧪")
            if categories.ui:     indicators.append("🎨")
            if categories.py_sdk: indicators.append("🐍")

            cat_str = " ".join(indicators) if indicators else ""

            row = [
                processed["date"],
                processed["author"],
                processed["title"][:47] + "..." if len(processed["title"]) > 50 else processed["title"],
                processed["line_diff"],
                processed["files"],
                cat_str,
                processed["url"],
            ]
            formatted_row = row_format.format(*row)

            if processed["draft"]:
                draft_rows.append(formatted_row)
            else:
                ready_rows.append(formatted_row)

        return "\n".join(ready_rows), "\n".join(draft_rows)

    def generate_digest(self) -> str:
        """Generate a digest of recent GitHub activity."""
        since_date = datetime.now(pytz.UTC) - timedelta(days=self.days)

        try:
            # Get recent activity with rate limit handling
            self._handle_rate_limit()
            commits = list(self.repo.get_commits(since=since_date, sha=self.branch))

            self._handle_rate_limit()
            prs = [pr for pr in self.repo.get_pulls(state="open")
                   if pr.updated_at >= since_date]

        except RateLimitExceededException:
            logger.exception("Rate limit exceeded while fetching initial data")
            self._handle_rate_limit()
            # Retry once after waiting
            commits = list(self.repo.get_commits(since=since_date, sha=self.branch))
            prs = [pr for pr in self.repo.get_pulls(state="open")
                   if pr.updated_at >= since_date]
        except GithubException as e:
            logger.exception(f"GitHub API error: {e}")
            raise

        # Format all content
        sections = [
            f"Activity Report for {self.repo.full_name} (Last {self.days} days)",
            "",
            "```",
            self.create_commit_table(commits, "Recent Commits"),
            "```",
            "",
            "```",
            self.create_pr_tables(prs, "Open Pull Requests")[0],  # Ready PRs
            "```",
            "",
            "```",
            self.create_pr_tables(prs, "Open Pull Requests")[1],  # Draft PRs
            "```",
            "",
            "Legend: 📚 Docs, 🧪 Tests, 🤖 Server, 🎨 UI, 📦 TS SDK, 🐍 Python SDK"
        ]

        return "\n".join(sections)


def main():
    """Main entry point for both CLI and Action modes."""
    parser = argparse.ArgumentParser(description="Generate GitHub activity digest")
    parser.add_argument(
        "--channel", default="weave-dev-digest", help="Slack channel name"
    )
    parser.add_argument(
        "--repo", default="wandb/weave", help="Repository name (owner/repo)"
    )
    parser.add_argument(
        "--days", type=int, default=7, help="Number of days to look back"
    )
    parser.add_argument("--branch", default="master", help="Branch to analyze")
    parser.add_argument(
        "--mode",
        choices=["local", "slack", "dry-run"],
        default="local",
        help="Run mode: local (rich tables), slack (send to Slack), or dry-run (preview Slack message)",
    )

    args = parser.parse_args()

    # Get required tokens
    github_token = os.getenv("GITHUB_TOKEN")
    if not github_token:
        raise ValueError("GITHUB_TOKEN environment variable is required")

    try:
        # Generate digest
        digest = GitHubDigest(
            token=github_token,
            repo=args.repo,
            days=args.days,
            branch=args.branch,
            local_mode=args.mode == "local",  # Only use rich output in local mode
        )

        if args.mode == "local":
            # Local mode - show rich tables
            digest.generate_digest()
        else:
            # Get Slack message content
            message = digest.generate_digest()

            if args.mode == "dry-run":
                # Preview mode - show what would be sent
                console.print("\n[bold]Preview of Slack message:[/bold]\n")
                console.print(message)
                console.print(f"\n[dim]Would be sent to channel: #{args.channel}[/dim]")
            else:
                # Slack mode - actually send it
                slack_token = os.getenv("SLACK_TOKEN")
                if not slack_token:
                    raise ValueError("SLACK_TOKEN environment variable is required")

                notifier = SlackNotifier(slack_token)
                notifier.send_message(args.channel, message)

    except Exception as e:
        logger.exception(f"Error: {str(e)}")
        raise


if __name__ == "__main__":
    main()
