import logging

import click

from weave.trace import settings

LOG_STRING = click.style("weave", fg="cyan", bold=True)

# Create and configure the logger
logger = logging.getLogger("weave")


# Create a custom formatter that adds the weave prefix
class WeaveFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        if not record.getMessage():
            return ""
        # First let the parent class handle the formatting
        formatted_message = super().format(record)
        # Then add the weave prefix to each line
        return "\n".join(
            [f"{LOG_STRING}: {line}" for line in formatted_message.split("\n")]
        )


def in_colab() -> bool:
    try:
        import google.colab  # noqa: F401

        return True  # noqa: TRY300
    except ImportError:
        return False


configured = False


def configure_logger() -> None:
    """Configure the root logger for Weave with custom formatting and log level."""
    global configured
    if configured:
        return
    configured = True
    # Create a console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(WeaveFormatter())

    # Add the handler to the logger
    logger.addHandler(console_handler)
    # Only disable propagation in colab to avoid double output
    if in_colab():
        logger.propagate = False

    # Set the log level based on environment variable
    log_level = settings.log_level()
    logger.setLevel(getattr(logging, log_level))


# Export the logger for use in other modules
__all__ = ["configure_logger", "logger"]
