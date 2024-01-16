import weave
from weave import artifact_fs

import numpy as np


@weave.type()
class MyTestObjWithOp:
    val: int

    @weave.op()
    def versioned_op(self, a: int) -> float:
        # Rely on the "import numpy as np" import
        return np.array([a, self.val]).mean()
