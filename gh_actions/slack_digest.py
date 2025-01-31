"""
GitHub Activity Digest Generator

This module generates comprehensive activity digests for GitHub repositories, with optional Slack integration.
It tracks commits, pull requests, and categorizes changes across different areas of the codebase.

Features:
- Tracks recent commits and pull requests
- Categorizes changes (docs, tests, server, UI, SDKs, etc.)
- Formats output for both console and Slack
- Handles GitHub API rate limiting
- Supports parallel processing for better performance

Usage:
    As a script:
        $ uv run gh_actions/slack_digest.py  # Console output
        $ uv run gh_actions/slack_digest.py --slack --channel weave-dev-digest  # Slack output

    As a GitHub Action:
        See .github/workflows/slack-digest.yml

Environment Variables:
    GITHUB_TOKEN: GitHub API token (required)
    SLACK_TOKEN: Slack API token (required for Slack output)

Dependencies are managed through the script directive:
"""

# /// script
# dependencies = [
#   "slack-sdk>=3.0.0",
#   "PyGithub",
#   "rich",
#   "python-dateutil",
#   "pytz",
#   "tabulate[widechars]",
# ]
# ///

from __future__ import annotations

import argparse
import logging
import os
import re
import time
from concurrent.futures import Future, ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime, timedelta
from re import Pattern
from typing import Any, Callable, Protocol

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
from tabulate import tabulate

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
class CategoryRule:
    """Rule for determining if a file belongs to a category.

    Attributes:
        name: Display name (e.g., "Docs")
        column_header: Short name for table header (e.g., "📚")
        emoji: Emoji indicator for visual representation
        matcher: Rule can be either a regex pattern or a callback function
    """

    name: str
    column_header: str
    emoji: str
    matcher: Pattern | Callable[[str], bool]


# Define all categories with their rules
CATEGORIES = [
    CategoryRule(
        name="Documentation",
        column_header="Docs",
        emoji="📚",
        matcher=re.compile(r"^docs/"),
    ),
    CategoryRule(
        name="Tests",
        column_header="Tests",
        emoji="🧪",
        matcher=lambda path: "test" in path,
    ),
    CategoryRule(
        name="Server",
        column_header="Server",
        emoji="🤖",
        matcher=re.compile(r"^weave/trace_server/"),
    ),
    CategoryRule(
        name="UI",
        column_header="UI",
        emoji="🎨",
        matcher=re.compile(
            r"^weave-js/src/components/PagePanelComponents/Home/Browse3/"
        ),
    ),
    CategoryRule(
        name="TypeScript SDK",
        column_header="TS",
        emoji="📦",
        matcher=re.compile(r"^sdks/node/"),
    ),
    CategoryRule(
        name="Python SDK",
        column_header="Py",
        emoji="🐍",
        matcher=lambda path: path.startswith("weave/")
        and not path.startswith("weave/trace_server/"),
    ),
]


@dataclass
class FileCategories:
    """Tracks which categories a set of files belongs to.

    This class analyzes files against predefined category rules and maintains
    a mapping of which categories match the files.

    Attributes:
        matches: Dictionary mapping category names to boolean match results
    """

    matches: dict[str, bool]

    @classmethod
    def analyze(
        cls, files: list[Any], categories: list[CategoryRule] = CATEGORIES
    ) -> FileCategories:
        """Analyze files against all category rules.

        Args:
            files: List of GitHub file objects to analyze
            categories: List of category rules to check against (defaults to CATEGORIES)

        Returns:
            FileCategories instance with match results
        """
        matches = {}
        paths = {f.filename for f in files}

        for category in categories:
            matches[category.name] = any(
                category.matcher.match(path)
                if isinstance(category.matcher, Pattern)
                else category.matcher(path)
                for path in paths
            )

        return cls(matches)

    def get_emoji(self, category_name: str) -> str:
        """Get emoji for category if it matches.

        Args:
            category_name: Name of the category to get emoji for

        Returns:
            Category emoji if matched, empty string otherwise
        """
        if not self.matches.get(category_name):
            return ""
        for cat in CATEGORIES:
            if cat.name == category_name:
                return cat.emoji
        return ""


class SlackNotifier:
    def __init__(self, token: str):
        """Initialize Slack notifier with authentication token."""
        self.client = WebClient(token=token)

    def validate_channel(self, channel: str) -> str:
        """Validate and format Slack channel name."""
        if not channel:
            raise ValueError("Channel name cannot be empty")
        return f"#{channel.lstrip('#')}"

    def send_message(self, channel: str, message: str) -> bool:
        """Send a single message to specified Slack channel."""
        channel = self.validate_channel(channel)
        try:
            self.client.chat_postMessage(channel=channel, text=message)
            print(f"Message sent to {channel}:")
            print(message)
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
            token: GitHub API token
            repo: Repository name in format 'owner/repo'
            days: Number of days to look back
            branch: Branch to analyze
            local_mode: Whether to show progress bars (True for local runs)
        """
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

    def analyze_paths(self, files) -> FileCategories:
        """Analyze file paths to determine which categories were modified."""
        return FileCategories.analyze(files)

    def format_line_diff(self, additions: int, deletions: int) -> str:
        """Format the line differences in a compact way."""

        def format_number(n: int) -> str:
            """Format a number compactly using K/M suffixes."""
            if n >= 1_000_000:
                return f"{n/1_000_000:.0f}M"  # Remove decimal for millions
            elif n >= 1_000:
                return f"{n/1_000:.0f}K"  # Remove decimal for thousands
            return str(n)

        # Format with no space between +/- to save space
        return f"+{format_number(additions)}/-{format_number(deletions)}"

    def process_items_parallel(
        self, items: list[Any], processor, description: str
    ) -> list[tuple[Any, Exception | None]]:
        """Process items in parallel using a thread pool."""
        results: list[tuple[Any, Exception | None]] = []
        cpu_count = os.cpu_count()
        max_workers = min(32, (cpu_count or 1) * 4)

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures: dict[Future, Any] = {}

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

    def truncate_title(self, title: str, max_length: int = 64) -> str:
        """Truncate title to specified length, adding ellipsis if needed."""
        if len(title) <= max_length:
            return title
        return title[: max_length - 3] + "..."

    def _get_base_row_data(
        self, item: Any, date_field: str, stats_source: Any = None
    ) -> dict:
        """Extract common row data from a GitHub item (commit or PR).

        Args:
            item: GitHub item (commit or PR)
            date_field: Name of the date field to use, can be a dot-separated path
            stats_source: Optional separate object to get stats from (for commits)

        Returns:
            Dictionary containing common row data
        """
        # Handle nested attribute access for date field
        current = item
        for attr in date_field.split("."):
            current = getattr(current, attr)
        date = current.strftime("%Y-%m-%d %H:%M")

        # Use stats from stats_source if provided, otherwise from item
        stats_obj = stats_source if stats_source is not None else item

        return {
            "date": date,
            "line_diff": self.format_line_diff(
                stats_obj.stats.additions, stats_obj.stats.deletions
            ),
            "files": str(stats_obj.stats.total),
            "url": stats_obj.html_url,
        }

    def _create_table_section(
        self,
        title: str,
        items: list,
        processor: Callable,
        headers: list[str],
        description: str,
        sort_by_date: bool = True,
    ) -> Section:
        """Create a table section from items.

        Args:
            title: Section title
            items: List of items to process
            processor: Function to process each item
            headers: Table headers
            description: Progress description
            sort_by_date: Whether to sort rows by date descending (default: True)

        Returns:
            Formatted Section object
        """
        results = self.process_items_parallel(items, processor, description)

        rows = []
        for processed, error in results:
            if error is not None:
                logger.warning(f"Skipping item due to error: {error}")
                continue

            categories = processed["categories"]
            row = [
                processed["date"],
                processed["author"],
                processed["message" if "message" in processed else "title"],
                processed["line_diff"],
                processed["files"],
            ]
            # Add category columns consistently
            row.extend(categories.get_emoji(cat.name) for cat in CATEGORIES)
            row.append(processed["url"])
            rows.append(row)

        # Sort rows by date descending if requested
        if sort_by_date and rows:
            rows.sort(key=lambda x: x[0], reverse=True)

        return Section(title=title, headers=headers, rows=rows)

    def process_commit(self, commit):
        """Process a single commit into row data.

        Args:
            commit: GitHub Commit object

        Returns:
            Dictionary containing processed commit data
        """
        # Pass the outer commit object as stats_source since it contains the stats
        base_data = self._get_base_row_data(
            commit.commit,  # GitCommit object for author/date
            "author.date",
            stats_source=commit,  # Outer commit object for stats
        )
        base_data.update(
            {
                "author": commit.author.login if commit.author else "Unknown",
                "message": self.truncate_title(commit.commit.message.split("\n")[0]),
                "categories": FileCategories.analyze(commit.files),
            }
        )
        return base_data

    def process_pr(self, pr):
        """Process a single PR into row data."""
        base_data = {
            "date": pr.updated_at.strftime("%Y-%m-%d %H:%M"),
            "line_diff": self.format_line_diff(pr.additions, pr.deletions),
            "files": str(pr.changed_files),
            "url": pr.html_url,
        }
        base_data.update(
            {
                "author": pr.user.login,
                "title": self.truncate_title(pr.title),
                "categories": self.analyze_paths(pr.get_files()),
                "draft": pr.draft,
            }
        )
        return base_data

    def _create_commit_section(self, commits) -> Section:
        """Create a section for commit information."""
        headers = ["Date Merged", "Author", "Message", "Line Diff", "Files"]
        headers.extend(cat.column_header for cat in CATEGORIES)
        headers.append("Link")

        return self._create_table_section(
            title="Recent Commits",
            items=commits,
            processor=self.process_commit,
            headers=headers,
            description="Processing commits...",
        )

    def _create_pr_sections(self, prs) -> tuple[Section, Section]:
        """Create sections for pull requests."""
        headers = ["Last Updated", "Author", "Title", "Line Diff", "Files"]
        headers.extend(cat.column_header for cat in CATEGORIES)
        headers.append("Link")

        # Sort PRs by updated_at descending
        sorted_prs = sorted(prs, key=lambda x: x.updated_at, reverse=True)
        results = self.process_items_parallel(
            sorted_prs, self.process_pr, "Processing pull requests..."
        )

        ready_rows = []
        draft_rows = []
        for processed, error in results:
            if error is not None:
                logger.warning(f"Skipping PR due to error: {error}")
                continue

            categories = processed["categories"]
            row = [
                processed["date"],
                processed["author"],
                processed["title"],
                processed["line_diff"],
                processed["files"],
            ]
            row.extend(categories.get_emoji(cat.name) for cat in CATEGORIES)
            row.append(processed["url"])

            if processed["draft"]:
                draft_rows.append(row)
            else:
                ready_rows.append(row)

        # Sort both ready and draft rows by date descending
        ready_rows.sort(key=lambda x: x[0], reverse=True)
        draft_rows.sort(key=lambda x: x[0], reverse=True)

        ready_section = Section(
            title="Open Pull Requests - Ready for Review",
            headers=headers,
            rows=ready_rows,
        )

        draft_section = Section(
            title="Open Pull Requests - In Progress", headers=headers, rows=draft_rows
        )

        return ready_section, draft_section

    def collect_sections(self) -> list[Section]:
        """Collect all sections with their data."""
        since_date = datetime.now(pytz.UTC) - timedelta(days=self.days)
        end_date = datetime.now(pytz.UTC)

        try:
            # Get recent activity with rate limit handling
            self._handle_rate_limit()
            commits = list(self.repo.get_commits(since=since_date, sha=self.branch))

            self._handle_rate_limit()
            prs = [
                pr
                for pr in self.repo.get_pulls(state="open")
                if pr.updated_at >= since_date
            ]

        except RateLimitExceededException:
            logger.exception("Rate limit exceeded while fetching initial data")
            self._handle_rate_limit()
            # Retry once after waiting
            commits = list(self.repo.get_commits(since=since_date, sha=self.branch))
            prs = [
                pr
                for pr in self.repo.get_pulls(state="open")
                if pr.updated_at >= since_date
            ]
        except GithubException as e:
            logger.exception(f"GitHub API error: {e}")
            raise

        # Create header section with date range and bold formatting
        header = Section(
            title=f"**Activity Report for {self.repo.full_name}**\n{since_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')} (Last {self.days} days)",
            headers=[],
            rows=[],
        )

        # Create data sections
        commit_section = self._create_commit_section(commits)
        ready_prs, draft_prs = self._create_pr_sections(prs)

        return [header, commit_section, ready_prs, draft_prs]


@dataclass
class Section:
    """A section of the digest containing a table and metadata.

    Attributes:
        title: Section heading
        headers: List of column headers
        rows: List of row data
        footer: Optional footer text
    """

    title: str
    headers: list[str]
    rows: list[list[Any]]
    footer: str = ""


class DigestFormatter(Protocol):
    """Protocol for formatting digest sections.

    This protocol defines the interface that all digest formatters must implement
    to provide consistent output formatting across different output types.
    """

    def format_section(self, section: Section) -> str:
        """Format a single section.

        Args:
            section: Section to format

        Returns:
            Formatted section string
        """
        ...

    def format_digest(self, sections: list[Section]) -> str:
        """Format the complete digest.

        Args:
            sections: List of sections to format

        Returns:
            Complete formatted digest string
        """
        ...


class TabulateFormatter:
    """Formats digest sections using tabulate.

    This formatter creates GitHub-flavored markdown tables using the tabulate library.
    It ensures consistent formatting across all sections while maintaining readability.
    """

    def format_section(self, section: Section) -> str:
        """Format a single section using tabulate.

        Args:
            section: Section to format

        Returns:
            Formatted section with title, table, and optional footer
        """
        table = tabulate(
            section.rows,
            headers=section.headers,
            tablefmt="pipe",  # Use GitHub-style markdown tables
            numalign="left",  # Left align numbers
            stralign="left",  # Left align strings
        )
        parts = [section.title, "", table]
        if section.footer:
            parts.extend(["", section.footer])
        return "\n".join(parts)

    def format_digest(self, sections: list[Section]) -> str:
        """Format the complete digest.

        Args:
            sections: List of sections to format

        Returns:
            Complete formatted digest as a string
        """
        formatted_sections = [self.format_section(section) for section in sections]
        return "\n\n".join(formatted_sections)


class DigestOutput(Protocol):
    """Protocol for outputting the digest.

    This protocol defines the interface that all output handlers must implement
    to provide consistent output behavior across different destinations.
    """

    def send(self, content: str) -> None:
        """Send the digest to the output destination.

        Args:
            content: Formatted digest content to send

        Raises:
            Any implementation-specific exceptions
        """
        pass


class ConsoleOutput:
    """Output digest to console using rich formatting."""

    def __init__(self, console: Console = console):
        """Initialize console output.

        Args:
            console: Rich console instance for output (defaults to global console)
        """
        self.console = console

    def send(self, content: str) -> None:
        """Send content to console with markdown code block formatting.

        Args:
            content: Formatted digest content to display
        """
        self.console.print("```")
        self.console.print(content)
        self.console.print("```")


class SlackOutput:
    """Output digest to Slack, handling message size limits.

    This class handles splitting large messages into appropriate chunks
    and ensures proper formatting is maintained across message boundaries.
    Respects both Slack's character limit (4000) and line limit for readability.
    """

    def __init__(
        self,
        token: str,
        channel: str,
        max_lines_per_block: int = 25,
        max_chars_per_block: int = 4000,
    ):
        """Initialize Slack output handler.

        Args:
            token: Slack API token
            channel: Target Slack channel
            max_lines_per_block: Maximum lines per message block (default: 25)
            max_chars_per_block: Maximum characters per message block (default: 4000)
        """
        self.notifier = SlackNotifier(token)
        self.channel = channel
        self.MAX_LINES_PER_BLOCK = max_lines_per_block
        self.MAX_CHARS_PER_BLOCK = max_chars_per_block

    def send(self, content: str) -> None:
        """Send content to Slack, splitting into appropriate chunks.

        The content is split into chunks that respect:
        1. Table boundaries (don't split in middle of table)
        2. Slack's character limit (4000)
        3. Line limit for readability (25)
        Tables are wrapped in code blocks for proper formatting.

        Args:
            content: Formatted digest content to send

        Raises:
            SlackApiError: If there's an error sending to Slack
        """
        lines = content.split("\n")
        current_chunk: list[str] = []
        current_char_count = 0
        in_table = False

        for line in lines:
            is_table_line = bool(line.strip()) and line.strip()[0] in "|+-"
            line_length = len(line) + 1  # +1 for newline

            # Start new chunk if:
            # 1. Current chunk is too long (lines), or
            # 2. Adding this line would exceed character limit, or
            # 3. We're transitioning between table and non-table content
            if (
                len(current_chunk) >= self.MAX_LINES_PER_BLOCK
                or current_char_count + line_length > self.MAX_CHARS_PER_BLOCK
                or (current_chunk and is_table_line != in_table)
            ):
                self._send_chunk(current_chunk, in_table)
                current_chunk = []
                current_char_count = 0

            current_chunk.append(line)
            current_char_count += line_length
            in_table = is_table_line

        if current_chunk:
            self._send_chunk(current_chunk, in_table)

    def _send_chunk(self, lines: list[str], is_table: bool) -> None:
        """Send a chunk of lines to Slack.

        Args:
            lines: List of lines to send
            is_table: Whether the chunk contains table content

        Raises:
            SlackApiError: If there's an error sending to Slack
        """
        if not lines:
            return

        content = "\n".join(lines)
        if is_table:
            content = f"```\n{content}\n```"

        # Verify final size is within limits (including code block markers if table)
        if len(content) > self.MAX_CHARS_PER_BLOCK:
            logger.warning(
                f"Chunk exceeds character limit ({len(content)} > {self.MAX_CHARS_PER_BLOCK})"
            )

        self.notifier.send_message(self.channel, content)


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
        "--slack",
        action="store_true",
        help="Send digest to Slack (default: print to console)",
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
            local_mode=True,
        )

        # Collect and format sections
        sections = digest.collect_sections()
        formatter = TabulateFormatter()
        content = formatter.format_digest(sections)

        # Output the digest
        if args.slack:
            slack_token = os.getenv("SLACK_TOKEN")
            if not slack_token:
                raise ValueError("SLACK_TOKEN environment variable is required")

            output = SlackOutput(slack_token, args.channel)
            output.send(content)
        else:
            output = ConsoleOutput()
            output.send(content)

    except Exception as e:
        logger.exception(f"Error: {str(e)}")
        raise


if __name__ == "__main__":
    main()
