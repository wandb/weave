"""This test should the patterns we need for our core ML types."""

import pytest
import dataclasses
import numpy as np

from .. import context_state as _context
import weave

_loading_builtins_token = _context.set_loading_built_ins()


@dataclasses.dataclass(frozen=True)
class LinearModelType(weave.types.ObjectType):
    input_type: weave.types.Type = weave.types.Any()
    output_type: weave.types.Type = weave.types.Any()

    def property_types(self):
        # Huh... this has the same interface as any function...
        return {
            "input_type": self.input_type,
            "output_type": self.output_type,
            "model_coefs": weave.types.List(weave.types.Float()),
        }


@weave.weave_class(weave_type=LinearModelType)
@dataclasses.dataclass(frozen=True)
class Model:
    input_type: weave.types.Type
    output_type: weave.types.Type
    model_coefs: list[float]

    @weave.op(
        input_type={"X": lambda input_type: input_type["self"].input_type},
        output_type=lambda input_type: input_type["self"].output_type,
    )
    def predict(self, X):
        poly1d_fn = np.poly1d(self.model_coefs)
        return poly1d_fn(X)


_context.clear_loading_built_ins(_loading_builtins_token)


@weave.op(
    input_type={
        "X": weave.types.List(weave.types.Int()),
        "y": weave.types.List(weave.types.Int()),
    },
    output_type=LinearModelType(),
)
def train(X, y):
    return Model(weave.type_of(X), weave.type_of(y), np.polyfit(X, y, 1))


def test_flow():
    train_data = weave.save(
        [
            {"X": 1, "y": 1},
            {"X": 2, "y": 3},
        ]
    )

    model = train(train_data.pick("X"), train_data.pick("y"))

    test_data = weave.save(
        [
            {"X": 9, "y": 15},
            {"X": 10, "y": 20},
        ]
    )
    output = model.predict(test_data.pick("X"))

    output = weave.use(output)
    assert output[0] == pytest.approx(17)
    assert output[1] == pytest.approx(19)

    # assert output[0].input == test_data["X"][0]
    # assert output[1].input == test_data["X"][1]

    # assert output.input == test_data["X"]

    # # .dataset? .table? .root?
    # assert output.input.table == test_data
