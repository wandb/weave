import logging
import os

import click

LOG_STRING = click.style("weave", fg="cyan", bold=True)

# Create and configure the logger
logger = logging.getLogger("weave")


# Create a custom formatter that adds the weave prefix
class WeaveFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        if not record.getMessage():
            return ""
        # Add the weave prefix to each line
        message = "\n".join(
            [f"{LOG_STRING}: {line}" for line in record.getMessage().split("\n")]
        )
        record.msg = message
        return super().format(record)


def configure_logger() -> None:
    """Configure the root logger for Weave with custom formatting and log level."""
    # Create a console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(WeaveFormatter())

    # Add the handler to the logger
    logger.addHandler(console_handler)

    # Set the log level based on environment variable
    log_level = os.getenv("WEAVE_LOG_LEVEL", "INFO").upper()
    logger.setLevel(getattr(logging, log_level))


# Export the logger for use in other modules
__all__ = ["configure_logger", "logger"]
