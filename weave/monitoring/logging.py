import logging

logger = logging.getLogger(__name__)


def configure_logging(level=logging.WARNING, logfile=None):
    """Configure logging for this library.

    Args:
        level: The log level to use. Defaults to logging.WARNING.
        logfile: If provided, log messages will be written to this file
            instead of standard output.
    """
    if logfile:
        handler = logging.FileHandler(logfile)
    else:
        handler = logging.StreamHandler()
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    handler.setFormatter(formatter)

    logger.handlers = []
    logger.addHandler(handler)
    logger.setLevel(level)
