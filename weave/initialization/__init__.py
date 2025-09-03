from .deferred_patcher import install_deferred_patches

# Install deferred patching mechanism
# This will:
# 1. Apply patches immediately if PIL or moviepy are already imported
# 2. Otherwise, install import hooks to apply patches when they are imported later
install_deferred_patches()

__all__: list[str] = []
