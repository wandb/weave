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
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional

import pytz
from github import Github
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
    "bright_red", "bright_green", "bright_yellow", "bright_blue",
    "bright_magenta", "bright_cyan", "orange3", "purple", "turquoise2",
    "deep_pink2", "spring_green1", "dark_orange", "deep_sky_blue1"
]

@dataclass
class ChangeCategories:
    """Tracks which categories of files were modified."""

    docs: bool = False        # Changes in ./docs
    server: bool = False      # Changes in ./weave/trace_server
    ts_sdk: bool = False      # Changes in ./sdks/node
    tests: bool = False       # Changes in test files
    ui: bool = False          # Changes in weave-js/src/components/PagePanelComponents/Home/Browse3
    py_sdk: bool = False      # Changes in ./weave (excluding trace_server)

@dataclass
class CategoryInfo:
    """Information about a category of changes."""

    emoji: str
    name: str
    path: str

# Define categories with their emojis and paths
CATEGORIES = {
    'docs': CategoryInfo('📚', 'Docs', './docs'),
    'tests': CategoryInfo('🧪', 'Tests', 'test'),
    'server': CategoryInfo('🤖', 'Server', './weave/trace_server'),
    'ui': CategoryInfo('🎨', 'UI', 'weave-js/src/components/PagePanelComponents/Home/Browse3'),
    'ts_sdk': CategoryInfo('📦', 'TS SDK', './sdks/node'),
    'py_sdk': CategoryInfo('🐍', 'Python SDK', './weave')
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

    def __init__(self, token: str, repo: str, days: int = 7, branch: str = "master", local_mode: bool = False):
        """Initialize GitHub digest generator.

        Args:
            token: GitHub personal access token
            repo: Repository name (owner/repo format)
            days: Number of days to look back
            branch: Branch to analyze
            local_mode: Whether to run in local mode with rich progress indicators
        """
        self.github = Github(token)
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

    def generate_digest(self) -> str:
        """Generate a digest of recent GitHub activity.
        
        Returns:
            Formatted digest message suitable for Slack
        """
        since_date = datetime.now(pytz.UTC) - timedelta(days=self.days)

        # Get recent activity
        commits = list(self.repo.get_commits(since=since_date, sha=self.branch))
        prs = [pr for pr in self.repo.get_pulls(state='open')
               if pr.updated_at >= since_date]

        # Format the digest
        digest = f"*Activity Report for {self.repo.full_name} (Last {self.days} days)*\n\n"

        # Add commit summary
        digest += f"*Recent Commits ({len(commits)}):*\n"
        for commit in commits[-5:]:  # Show last 5 commits
            author = commit.author.login if commit.author else "Unknown"
            message = commit.commit.message.split('\n')[0]
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
    parser.add_argument("--channel", default="weave-dev-digest", help="Slack channel name")
    parser.add_argument("--repo", default="wandb/weave", help="Repository name (owner/repo)")
    parser.add_argument("--days", type=int, default=7, help="Number of days to look back")
    parser.add_argument("--branch", default="master", help="Branch to analyze")
    parser.add_argument("--action", action="store_true", help="Run in GitHub Action mode (sends to Slack)")

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
            local_mode=not args.action  # Local mode is default
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
