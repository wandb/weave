from typing import Callable

LOG_ONCE_MESSAGE_SUFFIX = " (subsequent messages of this type will be suppressed)"
logged_messages = []


def log_once(log_method: Callable[[str], None], message: str) -> None:
    """Logs a message once, suppressing subsequent messages of the same type. This
    is useful for notifying the user about errors without spamming the logs.

    This is mostly useful for cases where the same error message might occur many times.
    For example, if an op fails to save, it is likely going to happen every time that op is
    called. Or, if we have an error in our patched iterator, then it likely happens every time
    we iterate over the result. This allows use to inform the user about the error without
    clogging up their logs.

    Args:
        log_method: The method to use to log the message. This should accept a string argument.
        message: The message to log.

    Example:
    ```python
    log_once(logger.error, "Failed to save op")
    ```
    """
    if message not in logged_messages:
        log_method(message + LOG_ONCE_MESSAGE_SUFFIX)
        logged_messages.append(message)
