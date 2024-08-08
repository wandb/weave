from importlib import metadata
from packaging import version

try:
    mistral_version = metadata.version("mistralai")
except metadata.PackageNotFoundError:
    raise ImportError("MistralAI is not installed. You can install it by doing `pip install mistralai`.")
else:
    if version.parse(mistral_version) < version.parse("1.0.0"):
        from .v0.mistral import mistral_patcher
        print(f"Using MistralAI version {mistral_version}. Please consider upgrading to version 1.0.0 or later.")
    else:
        from .v1.mistral import mistral_patcher
