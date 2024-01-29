"""Basic autopatching of trackable libraries.

This module should not require any dependencies beyond the standard library. It should
check if libraries are installed and imported and patch in the case that they are.
"""


def autopatch_openai() -> None:
    try:
        import openai  # type: ignore
    except ImportError:
        pass
    else:
        if openai.__version__ < "1":
            print(
                "To automatically track openai calls, upgrade the openai package to a version >= '1.0'"
            )
            return
        from weave.monitoring.openai import patch

        patch()


def autopatch() -> None:
    autopatch_openai()
