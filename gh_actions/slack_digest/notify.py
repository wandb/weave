"""Run this script with `uv run gh_actions/slack_digest/notify.py`"""

# This is a special comment block that uv uses to install dependencies
# /// script
# dependencies = [
#   "slack-sdk>=3.0.0",
# ]
# ///


import argparse
import logging
import os
from datetime import datetime

import pytz
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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
            response = self.client.chat_postMessage(
                channel=channel,
                text=message
            )
            logger.info(f"Message sent successfully to {channel}")
            return True
        except SlackApiError as e:
            logger.error(f"Failed to send message: {e.response['error']}")
            raise

def main():
    parser = argparse.ArgumentParser(description="Send notifications to Slack")
    parser.add_argument("--channel", default="general", help="Slack channel name")
    parser.add_argument("--message", required=True, help="Message to send")
    parser.add_argument("--timezone", default="UTC", help="Timezone for timestamp")

    args = parser.parse_args()

    # Get token from environment
    token = os.getenv("SLACK_TOKEN")
    if not token:
        raise ValueError("SLACK_TOKEN environment variable is required")

    try:
        notifier = SlackNotifier(token)
        current_time = datetime.now(pytz.timezone(args.timezone))
        formatted_message = f"[{current_time.strftime('%Y-%m-%d %H:%M %Z')}]\n{args.message}"

        notifier.send_message(args.channel, formatted_message)
    except Exception as e:
        logger.error(f"Error: {str(e)}")
        raise

if __name__ == "__main__":
    main()
