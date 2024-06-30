"""Utilities for working with IPython/Jupyter notebooks."""

import ast


def is_running_interactively():
    """Check if the code is running in an interactive environment."""
    try:
        from IPython import get_ipython

        return get_ipython() is not None
    except ModuleNotFoundError:
        return False


def get_notebook_source():
    """Get the source code of the running notebook."""
    from IPython import get_ipython

    shell = get_ipython()
    if shell is None:
        return "Not running in IPython/Jupyter environment"

    if not hasattr(shell, "user_ns"):
        return "Cannot access user namespace"

    # This is the list of input cells in the notebook
    in_list = shell.user_ns["In"]

    # Stitch them back into a single "file"
    full_source = "\n\n".join(cell for cell in in_list[1:] if cell)

    return full_source


def get_class_source(cls):
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

    raise ValueError(f"Class '{class_name}' not found in the notebook")
