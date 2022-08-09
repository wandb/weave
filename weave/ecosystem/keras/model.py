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
from tensorflow import keras
from keras.engine import keras_tensor
from tensorflow.python.framework import dtypes
import tensorflow as tf
from PIL import Image
import requests
import numpy as np

import weave
from weave.ops_primitives.image import PILImageType
from weave.weave_types import List, TypeRegistry


class DTYPE_NAME(Enum):
    NUMBER = "number"
    BOOL = "bool"
    STRING = "string"
    UNMAPPED = "unmapped"


# see https://www.tensorflow.org/api_docs/python/tf/dtypes
DTYPE_NAME_TO_TF_DTYPES: dict[DTYPE_NAME, list[dtypes.DType]] = {
    DTYPE_NAME.NUMBER: [
        dtypes.bfloat16,
        dtypes.double,
        dtypes.float16,
        dtypes.float32,
        dtypes.float64,
        dtypes.half,
        dtypes.int16,
        dtypes.int32,
        dtypes.int64,
        dtypes.int8,
        dtypes.qint16,
        dtypes.qint32,
        dtypes.qint8,
        dtypes.quint16,
        dtypes.quint8,
        dtypes.uint16,
        dtypes.uint32,
        dtypes.uint64,
        dtypes.uint8,
    ],
    DTYPE_NAME.BOOL: [dtypes.bool],
    DTYPE_NAME.STRING: [dtypes.string],
    DTYPE_NAME.UNMAPPED: [
        dtypes.complex128,
        dtypes.complex64,
        dtypes.resource,
        dtypes.variant,
    ],
}

DTYPE_NAME_TO_WEAVE_TYPE: dict[DTYPE_NAME, weave.types.Type] = {
    DTYPE_NAME.NUMBER: weave.types.Number(),
    DTYPE_NAME.BOOL: weave.types.Boolean(),
    DTYPE_NAME.STRING: weave.types.String(),
    DTYPE_NAME.UNMAPPED: weave.types.UnknownType(),
}

DTYPE_ENUM_TO_DTYPE_NAME: dict[int, DTYPE_NAME] = {}
for dtype_name, dtypes in DTYPE_NAME_TO_TF_DTYPES.items():
    for dtype in dtypes:
        DTYPE_ENUM_TO_DTYPE_NAME[dtype.as_datatype_enum] = dtype_name


@dataclass
class KerasTensorType(weave.types.Type):
    instance_classes = keras_tensor.KerasTensor
    instance_class = keras_tensor.KerasTensor

    shape: weave.types.Type = weave.types.Any()  # list[int | None]
    datatype_enum: weave.types.Type = weave.types.Any()  # int

    @classmethod
    def type_of_instance(cls, obj):
        # convert the list to a dict so we can take advantage of dict assignment
        shape_as_dict_type = {
            f"{k}": weave.types.NoneType()
            if v is None
            else weave.types.Const(weave.types.Number(), v)
            for k, v in enumerate(obj.shape.as_list())
        }
        return cls(
            shape=weave.types.TypedDict(shape_as_dict_type),
            datatype_enum=weave.types.Const(
                weave.types.Number(), obj.dtype.as_datatype_enum
            ),
        )

    # This is just a helper function for building the type of a KerasTensor
    @classmethod
    def from_list(
        cls: Type["KerasTensorType"],
        shape: list[Union[None, int]],
        dtype_name: DTYPE_NAME,
    ) -> "KerasTensorType":
        type_union_members = [
            weave.types.Const(weave.types.Number(), dtype.as_datatype_enum)
            for dtype in DTYPE_NAME_TO_TF_DTYPES[dtype_name]
        ]

        return cls(
            shape=weave.types.TypedDict(
                {
                    f"{shape_ndx}": (
                        weave.types.NoneType()
                        if dim is None
                        else weave.types.Const(weave.types.Number(), dim)
                    )
                    for shape_ndx, dim in enumerate(shape)
                }
            ),
            datatype_enum=weave.types.union(*type_union_members),  # type: ignore
        )


@dataclass
class KerasModel(weave.types.Type):
    instance_classes = keras.Model
    instance_class = keras.Model

    inputs_type: weave.types.Type = weave.types.Any()  # list[KerasTensorType]
    outputs_type: weave.types.Type = weave.types.Any()  # list[KerasTensorType]

    @classmethod
    def type_of_instance(cls, obj):
        inputs_as_dict = {
            f"{k}": TypeRegistry.type_of(v) for k, v in enumerate(obj.inputs)
        }
        outputs_as_dict = {
            f"{k}": TypeRegistry.type_of(v) for k, v in enumerate(obj.outputs)
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
        inputs_def: Optional[list[tuple[list[Union[None, int]], DTYPE_NAME]]] = None,
        outputs_def: Optional[list[tuple[list[Union[None, int]], DTYPE_NAME]]] = None,
    ) -> "KerasModel":
        inputs = (
            weave.types.TypedDict(
                {
                    f"{input_ndx}": KerasTensorType.from_list(shape[0], shape[1])
                    for input_ndx, shape in enumerate(inputs_def)
                }
            )
            if inputs_def is not None
            else weave.types.Any()
        )
        outputs = (
            weave.types.TypedDict(
                {
                    f"{input_ndx}": KerasTensorType.from_list(shape[0], shape[1])
                    for input_ndx, shape in enumerate(outputs_def)
                }
            )
            if outputs_def is not None
            else weave.types.Any()
        )
        return cls(inputs, outputs)


# def call_string_output_type(input_types):
#     dimensions = 0
#     for input_type in input_types:

# TODO: Figure out batching - we already have the `None` in the batch index!
@weave.op(
    input_type={
        "model": KerasModel.make_type([([None, 1], DTYPE_NAME.STRING)]),
        "input_str": weave.types.String(),
    },
    # TODO: Get the shapes correct
    output_type=lambda input_types: DTYPE_NAME_TO_WEAVE_TYPE[
        DTYPE_ENUM_TO_DTYPE_NAME[
            input_types["model"].outputs_type.property_types["0"].datatype_enum.val
        ]
    ],
)
def call_string(model, input_str):
    # TODO: this double [0][0] is a smell. the first one gets into the batch and
    # the second one goes into the first result. this is really not ideal.
    return model.predict(tf.constant([input_str])).tolist()[0][0]


## The following op (image_classification) is just an example, it needs to be generalized
# before using it in production.
# TODO: figure out how to do this class lookup as part of the model
CLASS_NAMES = [
    "airplane",
    "automobile",
    "bird",
    "cat",
    "deer",
    "dog",
    "frog",
    "horse",
    "ship",
    "truck",
]
# TODO: Make this work with any image size?
@weave.op(
    input_type={
        "model": KerasModel.make_type(
            [([None, 32, 32, 3], DTYPE_NAME.NUMBER)], [([None, 10], DTYPE_NAME.NUMBER)]
        ),
        "url": weave.types.String(),
    },
    output_type=weave.types.TypedDict(
        {"image": PILImageType(32, 32), "prediction": weave.types.String()}
    ),
)
def image_classification(model, url):
    # TODO: maybe this should be it's own inner op?
    im = Image.open(requests.get(url, stream=True).raw)
    class_name = CLASS_NAMES[
        np.argmax(
            model.predict(
                tf.constant([np.asarray(im.resize((32, 32), Image.ANTIALIAS)) / 255.0])
            )[0]
        ).item()
    ]
    return {"image": im, "prediction": class_name}
