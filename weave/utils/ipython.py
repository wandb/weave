"""Utilities for working with IPython/Jupyter notebooks."""

import ast
import sys
from collections.abc import Callable


class NotInteractiveEnvironmentError(Exception): ...


class ClassNotFoundError(ValueError): ...


def _get_ipython():
    # Avoid importing IPython in non-interactive CLI runs since it may
    # initialize prompt_toolkit and mutate terminal mode (e.g., break Textual apps).
    if "IPython" not in sys.modules:
        return None
    try:
        from IPython import get_ipython
    except Exception:
        return None
    return get_ipython()


def is_running_interactively() -> bool:
    """Check if the code is running in an interactive environment."""
    return _get_ipython() is not None


def get_notebook_source() -> str:
    """Get the source code of the running notebook."""
    shell = _get_ipython()
    if shell is None:
        raise NotInteractiveEnvironmentError

    if not hasattr(shell, "user_ns"):
        raise AttributeError("Cannot access user namespace")

    # This is the list of input cells in the notebook
    in_list = shell.user_ns["In"]

    # Stitch them back into a single "file"
    full_source = "\n\n".join(cell for cell in in_list[1:] if cell)

    return full_source


def get_class_source(cls: Callable) -> str:
    """Get the latest source definition of a class in the notebook."""
    notebook_source = get_notebook_source()
    tree = ast.parse(notebook_source)
    class_name = cls.__name__

    # We need to walk the entire tree and get the last one since that's the most version of the cls
    segment = None
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            segment = ast.get_source_segment(notebook_source, node)

    if segment is not None:
        return segment

    raise ClassNotFoundError(f"Class '{class_name}' not found in the notebook")
