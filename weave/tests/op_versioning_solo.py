import weave
from weave import artifact_fs
import numpy as np


@weave.op()
def solo_versioned_op(a: int) -> float:
    # Rely on the "import numpy as np" import
    return np.array([a, a]).mean()
