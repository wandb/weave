# Keeping this file for now to avoid breaking changes.
# In future, users should import all scoring functionality from weave.scorers
import warnings

from weave.scorers import *

warnings.warn(
    "Importing from weave.flow.scorer is deprecated. "
    "Please import from weave.scorers in the future.",
    DeprecationWarning,
    stacklevel=2,
)
