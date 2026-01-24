"""Loading spinner for weave analytics CLI."""

import itertools
import sys
import threading
import time
from typing import Callable


class AnalyticsSpinner:
    """Animated spinner for long-running operations."""

    def __init__(self, message: str = "Processing") -> None:
        """Initialize the spinner.

        Args:
            message: The message to display alongside the spinner
        """
        self.frames = [
            "W E A V E",
            "E A V E W",
            "A V E W E",
            "V E W E A",
            "E W E A V",
        ]
        self.message = message
        self.spinner = itertools.cycle(self.frames)
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._first_frame_shown = False

    def _colorize_frame(self, frame: str) -> str:
        """Colorize a spinner frame."""
        colored_frame = ""
        for i, char in enumerate(frame):
            if char == " ":
                colored_frame += " "
            elif i % 4 == 0:  # W and V positions
                colored_frame += f"\033[95m{char}\033[0m"  # bright_magenta
            elif i % 4 == 2:  # E and E positions
                colored_frame += f"\033[96m{char}\033[0m"  # cyan
            else:  # A position
                colored_frame += char  # white
        return colored_frame

    def _spin(self) -> None:
        """Internal method to run the spinner animation."""
        if not self._first_frame_shown:
            sys.stderr.write("\n")
            frame = next(self.spinner)
            colored_frame = self._colorize_frame(frame)
            sys.stderr.write(f"{colored_frame}  {self.message}...\n\n")
            sys.stderr.flush()
            self._first_frame_shown = True

        while not self._stop_event.is_set():
            frame = next(self.spinner)
            colored_frame = self._colorize_frame(frame)

            # Move cursor up 2 lines, clear line, print spinner
            sys.stderr.write("\033[2A\r" + " " * 80 + "\r")
            sys.stderr.write(f"{colored_frame}  {self.message}...\n\n")
            sys.stderr.flush()
            time.sleep(0.15)

    def start(self) -> None:
        """Start the spinner in a background thread."""
        if self._thread is not None and self._thread.is_alive():
            return

        self._stop_event.clear()
        self._first_frame_shown = False
        self._thread = threading.Thread(target=self._spin, daemon=True)
        self._thread.start()

    def stop(self, final_message: str | None = None, success: bool = True) -> None:
        """Stop the spinner and optionally display a final message.

        Args:
            final_message: Optional message to display after stopping
            success: If True, shows a success indicator; if False, shows failure
        """
        if self._thread is None:
            return

        self._stop_event.set()
        self._thread.join(timeout=1.0)

        # Move cursor up 2 lines and clear
        sys.stderr.write("\033[2A\r" + " " * 80 + "\r")
        sys.stderr.flush()

        if final_message:
            if success:
                sys.stderr.write(f"\033[95m✓\033[0m {final_message}\n")
            else:
                sys.stderr.write(f"\033[91m✗\033[0m {final_message}\n")
            sys.stderr.flush()
        else:
            sys.stderr.write("\n")
            sys.stderr.flush()

    def update_message(self, new_message: str) -> None:
        """Update the spinner message while it's running."""
        self.message = new_message

    def __enter__(self) -> "AnalyticsSpinner":
        """Context manager entry - starts the spinner."""
        self.start()
        return self

    def __exit__(
        self,
        exc_type: type | None,
        exc_val: Exception | None,
        exc_tb: object,
    ) -> None:
        """Context manager exit - stops the spinner."""
        success = exc_type is None
        self.stop(success=success)


def with_spinner(message: str = "Processing") -> Callable:
    """Decorator to show a spinner while a function executes.

    Usage:
        @with_spinner("Loading data")
        def my_function():
            time.sleep(3)
            return "done"
    """
    from typing import Any

    def decorator(func: Callable) -> Callable:
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            spinner = AnalyticsSpinner(message)
            spinner.start()
            try:
                result = func(*args, **kwargs)
                spinner.stop(f"{message} complete", success=True)
                return result
            except Exception:
                spinner.stop(f"{message} failed", success=False)
                raise
        return wrapper
    return decorator
