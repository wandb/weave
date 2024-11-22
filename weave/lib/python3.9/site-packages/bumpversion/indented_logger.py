"""A logger adapter that adds an indent to the beginning of each message."""

import logging
from contextvars import ContextVar
from typing import Any, MutableMapping, Optional, Tuple

CURRENT_INDENT = ContextVar("current_indent", default=0)


class IndentedLoggerAdapter(logging.LoggerAdapter):
    """
    Logger adapter that adds an indent to the beginning of each message.

    Parameters:
        logger: The logger to adapt.
        extra: Extra values to add to the logging context.
        depth: The number of `indent_char` to generate for each indent level.
        indent_char: The character or string to use for indenting.
        reset: `True` if the indent level should be reset to zero.
    """

    def __init__(
        self,
        logger: logging.Logger,
        extra: Optional[dict] = None,
        depth: int = 2,
        indent_char: str = " ",
        reset: bool = False,
    ):
        super().__init__(logger, extra or {})
        self._depth = depth
        self._indent_char = indent_char
        if reset:
            self.reset()

    @property
    def current_indent(self) -> int:
        """
        The current indent level.
        """
        return CURRENT_INDENT.get()

    def indent(self, amount: int = 1) -> None:
        """
        Increase the indent level by `amount`.
        """
        CURRENT_INDENT.set(CURRENT_INDENT.get() + amount)

    def dedent(self, amount: int = 1) -> None:
        """
        Decrease the indent level by `amount`.
        """
        CURRENT_INDENT.set(max(0, CURRENT_INDENT.get() - amount))

    def reset(self) -> None:
        """
        Reset the indent level to zero.
        """
        CURRENT_INDENT.set(0)

    @property
    def indent_str(self) -> str:
        """
        The indent string.
        """
        return (self._indent_char * self._depth) * CURRENT_INDENT.get()

    def process(self, msg: str, kwargs: Optional[MutableMapping[str, Any]]) -> Tuple[str, MutableMapping[str, Any]]:
        """
        Process the message and add the indent.

        Args:
            msg: The logging message.
            kwargs: Keyword arguments passed to the logger.

        Returns:
            A tuple containing the message and keyword arguments.
        """
        msg = self.indent_str + msg

        return msg, kwargs
