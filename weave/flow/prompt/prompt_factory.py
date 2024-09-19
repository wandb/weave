import inspect
import os
from typing import Any

from weave.flow.prompt.prompt import Prompt


class PromptFactory:
    """A singleton for creating Prompt objects."""

    def __add__(self, other: Any) -> Prompt:
        frame = inspect.currentframe().f_back
        file_name = os.path.splitext(os.path.basename(frame.f_code.co_filename))[0]
        name = f"prompt_{file_name}_line{frame.f_lineno}"
        return Prompt(name=name) + other

    def __iadd__(self, other: Any) -> None:
        raise NotImplementedError(
            "PromptFactory cannot be modified. Use '+' operator instead."
        )


p = PromptFactory()
