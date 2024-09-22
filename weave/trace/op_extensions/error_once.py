from typing import Callable

LOG_ONCE_MESSAGE_SUFFIX = " (subsequent messages of this type will be suppressed)"
logged_messages = []


def log_once(log_method: Callable[[str], None], message: str) -> None:
    """Logs a message once, suppressing subsequent messages of the same type. This
    is useful for notifying the user about errors without spamming the logs."""
    if message not in logged_messages:
        log_method(message + LOG_ONCE_MESSAGE_SUFFIX)
        logged_messages.append(message)
