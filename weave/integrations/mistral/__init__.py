from importlib import metadata

from packaging import version

try:
    mistral_version = metadata.version("mistralai")
except metadata.PackageNotFoundError:
    mistral_version = "1.0"  # we need to return a patching function

if version.parse(mistral_version) < version.parse("1.0.0"):
    from .v0.mistral import get_mistral_patcher  # noqa: F401

    print(
        f"Using MistralAI version {mistral_version}. Please consider upgrading to version 1.0.0 or later."
    )
else:
    from .v1.mistral import get_mistral_patcher  # noqa: F401
