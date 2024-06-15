import numpy as np

import weave
from weave.old_weave import artifact_fs


@weave.op()
def solo_versioned_op(a: int) -> float:
    # Rely on the "import numpy as np" import
    return np.array([a, a]).mean()
