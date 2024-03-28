from typing import Callable
from weave.flow.obj import Object


class Model(Object):
    # TODO: should be infer: Callable
    def get_infer_method(self) -> Callable:
        for infer_method_names in ("predict", "infer", "forward"):
            infer_method = getattr(self, infer_method_names, None)
            if infer_method:
                return infer_method
        raise ValueError(
            f"Model {self} does not have a predict, infer, or forward method."
        )


def get_infer_method(model: Model) -> Callable:
    for infer_method_names in ("predict", "infer", "forward"):
        infer_method = getattr(model, infer_method_names, None)
        if infer_method:
            return infer_method
    raise ValueError(
        f"Model {model} does not have a predict, infer, or forward method."
    )
