"""
This file contains the Weave definition for KerasModel, allowing users to
save & publish Keras models. This handles serializations as well as extracting
the type definition for the model (input and output tensors). This is a work
in progress.

TODOS:
    - [ ] Add a single `call` method to the model class where the input data type is
        dependent on the model type. Shawn has ideas around how to do this (to make the
        type of arguments dependent on previous arguments). Moreover, the return type
        will also be dependent on the model. Currently we have a nasty `call_string_to_number` and `call_string_to_string` 
        as placeholders.
    - [ ] Figure out the correct way to do batching. There are two considerations:
        1. We allow tensors to have any number of `None` dimensions. We may want to remove this allowance, or restrict to just a single `None` dimension.
        2. We should make the `call*` functions mappable and if the modle has a batch dimension, bulk call on the model. - right now we just hard-code single batches.
    - [ ] The `image_classification` method is purely an example. It has some issues:
        1. The pre- and post- processing is hard coded for the example model - we need a way to properly handle a DAG/Series of transforms.
        2. The input is a URL - we need a way to nicely interop with the rest of the Images in our ecosystem.
"""


from dataclasses import dataclass
from enum import Enum
from typing import Optional, Type, Union
import typing
from tensorflow import keras
from keras.engine import keras_tensor
from tensorflow.python.framework import dtypes

import weave


class DTYPE_NAME(Enum):
    NUMBER = "number"
    BOOL = "bool"
    STRING = "string"
    UNMAPPED = "unmapped"


# see https://www.tensorflow.org/api_docs/python/tf/dtypes
DTYPE_TO_TYPE: dict[dtypes.bfloat16, weave.types.Type] = {
    dtypes.bfloat16: weave.types.Number(),
    dtypes.double: weave.types.Number(),
    dtypes.float16: weave.types.Number(),
    dtypes.float32: weave.types.Number(),
    dtypes.float64: weave.types.Number(),
    dtypes.half: weave.types.Number(),
    dtypes.int16: weave.types.Number(),
    dtypes.int32: weave.types.Number(),
    dtypes.int64: weave.types.Number(),
    dtypes.int8: weave.types.Number(),
    dtypes.qint16: weave.types.Number(),
    dtypes.qint32: weave.types.Number(),
    dtypes.qint8: weave.types.Number(),
    dtypes.quint16: weave.types.Number(),
    dtypes.quint8: weave.types.Number(),
    dtypes.uint16: weave.types.Number(),
    dtypes.uint32: weave.types.Number(),
    dtypes.uint64: weave.types.Number(),
    dtypes.uint8: weave.types.Number(),
    dtypes.bool: weave.types.Boolean(),
    dtypes.string: weave.types.String(),
    dtypes.complex128: weave.types.UnknownType(),
    dtypes.complex64: weave.types.UnknownType(),
    dtypes.resource: weave.types.UnknownType(),
    dtypes.variant: weave.types.UnknownType(),
}


def shape_to_dict(shape: typing.List[typing.Optional[int]]) -> weave.types.TypedDict:
    return weave.types.TypedDict(
        {
            f"{shape_ndx}": (
                weave.types.NoneType()
                if dim is None
                else weave.types.Const(weave.types.Number(), dim)
            )
            for shape_ndx, dim in enumerate(shape)
        }
    )


def shape_to_list(
    shape: typing.List[typing.Optional[int]], inner_type: weave.types.Type
) -> weave.types.Type:
    if len(shape) == 0:
        return inner_type
    else:
        # Once List supports length params, add it here
        return weave.types.List(shape_to_list(shape[1:], inner_type))


@dataclass(frozen=True)
class KerasTensorType(weave.types.Type):
    instance_classes = keras_tensor.KerasTensor
    instance_class = keras_tensor.KerasTensor

    shape: weave.types.Type = weave.types.Any()
    data_type: weave.types.Type = weave.types.Any()
    # Temporary type field to hold the "vector" like type
    weave_vector_type: weave.types.Type = weave.types.Any()

    @classmethod
    def type_of_instance(cls, obj):
        return cls(
            shape=shape_to_dict(obj.shape.as_list()),
            data_type=DTYPE_TO_TYPE[obj.dtype],
            weave_vector_type=shape_to_list(
                obj.shape.as_list(), DTYPE_TO_TYPE[obj.dtype]
            ),
        )

    # This is just a helper function for building the type of a KerasTensor
    @classmethod
    def from_list(
        cls: Type["KerasTensorType"],
        shape: list[Union[None, int]],
        data_type: weave.types.Type = weave.types.Any(),
    ) -> "KerasTensorType":
        return cls(
            shape=shape_to_dict(shape),
            data_type=data_type,
            weave_vector_type=shape_to_list(shape, data_type),
        )


@dataclass(frozen=True)
class KerasModel(weave.types.Type):
    instance_classes = keras.Model
    instance_class = keras.Model

    inputs_type: weave.types.Type = weave.types.Any()  # list[KerasTensorType]
    outputs_type: weave.types.Type = weave.types.Any()  # list[KerasTensorType]

    @classmethod
    def type_of_instance(cls, obj):
        inputs_as_dict = {
            f"{k}": weave.types.TypeRegistry.type_of(v)
            for k, v in enumerate(obj.inputs)
        }
        outputs_as_dict = {
            f"{k}": weave.types.TypeRegistry.type_of(v)
            for k, v in enumerate(obj.outputs)
        }
        return cls(
            weave.types.TypedDict(inputs_as_dict),
            weave.types.TypedDict(outputs_as_dict),
        )

    def save_instance(self, obj, artifact, name):
        with artifact.new_dir(f"{name}") as dirpath:
            obj.save(dirpath)

    def load_instance(self, artifact, name, extra=None):
        return keras.models.load_model(artifact.path(name))

    # This is just a helper function for building the type of a KerasModel
    @classmethod
    def make_type(
        cls: Type["KerasModel"],
        inputs_def: Optional[
            list[typing.Union[KerasTensorType, weave.types.Any]]
        ] = None,
        outputs_def: Optional[
            list[typing.Union[KerasTensorType, weave.types.Type]]
        ] = None,
    ) -> "KerasModel":
        inputs = (
            weave.types.TypedDict(
                {f"{input_ndx}": t for input_ndx, t in enumerate(inputs_def)}
            )
            if inputs_def is not None
            else weave.types.Any()
        )
        outputs = (
            weave.types.TypedDict(
                {f"{input_ndx}": t for input_ndx, t in enumerate(outputs_def)}
            )
            if outputs_def is not None
            else weave.types.Any()
        )
        return cls(inputs, outputs)


def byte_vector_to_string(maybe_byte_vector: typing.Any) -> typing.Union[list, str]:
    if isinstance(maybe_byte_vector, bytes):
        return maybe_byte_vector.decode("utf-8")
    elif isinstance(maybe_byte_vector, list):
        return [byte_vector_to_string(item) for item in maybe_byte_vector]
    else:
        return maybe_byte_vector


# Remaining limitations:
# - Batching is hard coded
# - Input type is hard coded
# - Single output and single input layer is hard coded
# - Vectors are not sized
@weave.op(
    input_type={
        "model": KerasModel.make_type(
            [KerasTensorType.from_list([None, 1], weave.types.String())],
            [weave.types.Any()],
        ),
        "input": weave.types.String(),
    },
    output_type=lambda input_types: input_types["model"]
    .outputs_type.property_types["0"]
    .weave_vector_type.object_type,
)
def call_string(model, input):
    res = model.predict([[input]]).tolist()[0]
    # Special case for strings: we need to convert the bytes to a string
    return byte_vector_to_string(res)


# Added back by Shawn to make notebook work for now.
# call_string has a callable output type. WeaveJS doesn't seem to be able
# to make use of it.
# TODO: remove
@weave.op(
    input_type={
        "model": KerasModel.make_type(
            [KerasTensorType.from_list([None, 1], weave.types.String())],
            [weave.types.String()],
        ),
        "input": weave.types.String(),
    },
)
def call_string_to_number(model, input) -> int:
    return model.predict([[input]]).tolist()[0][0]
