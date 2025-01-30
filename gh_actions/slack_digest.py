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

import argparse
import logging
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, List, Optional, Tuple

import pytz
import urllib3
from github import Github
from rich.console import Console
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
)
from rich.table import Table
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
        """Initialize GitHub digest generator.

        Args:
            token: GitHub personal access token
            repo: Repository name (owner/repo format)
            days: Number of days to look back
            branch: Branch to analyze
            local_mode: Whether to run in local mode with rich progress indicators (default: True)
        """
        # Configure connection pool for parallel requests
        self.pool_manager = urllib3.PoolManager(maxsize=32)
        self.github = Github(token, pool_size=32)
        self.repo = self.github.get_repo(repo)
        self.days = days
        self.branch = branch
        self.local_mode = local_mode
        self.progress = None

    def _get_progress(self) -> Optional[Progress]:
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
        self, items: List[Any], processor, description: str
    ) -> List[Tuple[Any, Exception]]:
        """Process items in parallel using a thread pool.

        Args:
            items: List of items to process
            processor: Function that processes a single item
            description: Description for progress bar

        Returns:
            List of (processed_item, exception) tuples. Exception is None if successful
        """
        results = []

        with ThreadPoolExecutor(max_workers=min(32, os.cpu_count() * 4)) as executor:
            futures = {executor.submit(processor, item): item for item in items}

            with self._get_progress() as progress:
                if progress:
                    task = progress.add_task(description, total=len(items))

                for future in as_completed(futures):
                    try:
                        result = future.result()
                        results.append((result, None))
                    except Exception as e:
                        original_item = futures[future]
                        results.append((original_item, e))
                        logger.warning(f"Error processing item: {e}")

                    if progress:
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

    def create_commit_table(self, commits, title: str) -> Table:
        """Create a rich table for displaying commit information."""
        table = Table(title=title)
        table.add_column("Date", style="cyan")
        table.add_column("Author", style="green")
        table.add_column("Message", style="white")
        table.add_column("Line Diff", style="yellow")
        table.add_column("Files", style="yellow")
        for cat in CATEGORIES.values():
            table.add_column(f"{cat.emoji} {cat.name}", justify="center")
        table.add_column("Link", style="blue")

        # Process commits in parallel
        results = self.process_items_parallel(
            commits, self.process_commit, "Processing commits..."
        )

        for processed, error in results:
            if error:
                logger.warning(f"Skipping commit due to error: {error}")
                continue

            categories = processed["categories"]
            row = [
                processed["date"],
                processed["author"],
                processed["message"],
                processed["line_diff"],
                processed["files"],
                "📚" if categories.docs else "",
                "🧪" if categories.tests else "",
                "🤖" if categories.server else "",
                "🎨" if categories.ui else "",
                "📦" if categories.ts_sdk else "",
                "🐍" if categories.py_sdk else "",
                f"[link={processed['url']}]View[/link]",
            ]
            table.add_row(*row)

        return table

    def create_pr_tables(self, prs, title_prefix: str) -> tuple[Table, Table]:
        """Create tables for pull requests."""
        ready_table = Table(title=f"{title_prefix} - Ready for Review")
        draft_table = Table(title=f"{title_prefix} - In Progress")

        for table in [ready_table, draft_table]:
            table.add_column("Updated", style="cyan")
            table.add_column("Author", style="green")
            table.add_column("Title", style="white")
            table.add_column("Line Diff", style="yellow")
            table.add_column("Files", style="yellow")
            for cat in CATEGORIES.values():
                table.add_column(f"{cat.emoji} {cat.name}", justify="center")
            table.add_column("Link", style="blue")

        sorted_prs = sorted(prs, key=lambda x: x.updated_at, reverse=True)

        # Process PRs in parallel
        results = self.process_items_parallel(
            sorted_prs, self.process_pr, "Processing pull requests..."
        )

        for processed, error in results:
            if error:
                logger.warning(f"Skipping PR due to error: {error}")
                continue

            categories = processed["categories"]
            row = [
                processed["date"],
                processed["author"],
                processed["title"],
                processed["line_diff"],
                processed["files"],
                "📚" if categories.docs else "",
                "🧪" if categories.tests else "",
                "🤖" if categories.server else "",
                "🎨" if categories.ui else "",
                "📦" if categories.ts_sdk else "",
                "🐍" if categories.py_sdk else "",
                f"[link={processed['url']}]View[/link]",
            ]

            target_table = draft_table if processed["draft"] else ready_table
            target_table.add_row(*row)

        return ready_table, draft_table

    def create_legend(self) -> Table:
        """Create a table explaining the category indicators."""
        legend = Table(title="Change Categories", show_header=False)
        for cat in CATEGORIES.values():
            legend.add_row(cat.emoji, f"Changes in {cat.path}")
        return legend

    def generate_digest(self) -> str:
        """Generate a digest of recent GitHub activity."""
        since_date = datetime.now(pytz.UTC) - timedelta(days=self.days)

        # Get recent activity
        commits = list(self.repo.get_commits(since=since_date, sha=self.branch))
        prs = [
            pr
            for pr in self.repo.get_pulls(state="open")
            if pr.updated_at >= since_date
        ]

        if self.local_mode:
            # Generate rich tables for local display
            commit_table = self.create_commit_table(
                commits, f"Recent Commits (Last {self.days} days)"
            )
            ready_table, draft_table = self.create_pr_tables(prs, "Open Pull Requests")

            # Return formatted tables for console display
            console.print(commit_table)
            console.print("\n")
            console.print(ready_table)
            console.print("\n")
            console.print(draft_table)
            console.print("\n")
            console.print(self.create_legend())
            return ""  # Console output already handled
        else:
            # Generate plain text for Slack
            # ... existing Slack message formatting code ...
            return self._generate_slack_digest(commits, prs)

    def _generate_slack_digest(self, commits, prs) -> str:
        """Generate a plain text digest suitable for Slack."""
        digest = (
            f"*Activity Report for {self.repo.full_name} (Last {self.days} days)*\n\n"
        )

        # Add commit summary
        digest += f"*Recent Commits ({len(commits)}):*\n"
        for commit in commits[-5:]:  # Show last 5 commits
            author = commit.author.login if commit.author else "Unknown"
            message = commit.commit.message.split("\n")[0]
            digest += f"• {author}: {message}\n"

        # Add PR summary
        ready_prs = [pr for pr in prs if not pr.draft]
        draft_prs = [pr for pr in prs if pr.draft]

        digest += f"\n*Open PRs Ready for Review ({len(ready_prs)}):*\n"
        for pr in ready_prs:
            digest += f"• {pr.user.login}: {pr.title}\n"

        digest += f"\n*PRs In Progress ({len(draft_prs)}):*\n"
        for pr in draft_prs:
            digest += f"• {pr.user.login}: {pr.title}\n"

        return digest


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
        "--action",
        action="store_true",
        help="Run in GitHub Action mode (sends to Slack)",
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
            local_mode=not args.action,  # Local mode is default
        )

        message = digest.generate_digest()

        if args.action:
            # In action mode, send to Slack
            slack_token = os.getenv("SLACK_TOKEN")
            if not slack_token:
                raise ValueError("SLACK_TOKEN environment variable is required")

            notifier = SlackNotifier(slack_token)
            notifier.send_message(args.channel, message)
        else:
            # In local mode (default), just print to console
            console.print(message)

    except Exception as e:
        logger.exception(f"Error: {str(e)}")
        raise


if __name__ == "__main__":
    main()
