import numpy as np

import weave


class MyTestObjWithOp(weave.Object):
    val: int

    @weave.op()
    def versioned_op(self, a: int) -> float:
        # Rely on the "import numpy as np" import
        return np.array([a, self.val]).mean()
