import dataclasses
import pickle
import datasets as hf_datasets
import transformers
import torch

import weave
from . import pytorch


class HFDatasetType(weave.types.ObjectType):
    name = "hf-dataset"

    def property_types(self):
        return {"name": weave.types.String()}


@weave.weave_class(weave_type=HFDatasetType)
class HFDataset:
    def __init__(self, name):
        self.name = name

    @weave.op(
        input_type={
            "self": HFDatasetType(),
        },
        output_type=weave.types.TypedDict(
            {
                "description": weave.types.String(),
                "homepage": weave.types.String(),
                "download_size": weave.types.Int(),
                "version": weave.types.String(),
            }
        ),
    )
    def info(self):
        dataset_builder = hf_datasets.load_dataset_builder(self.name)
        info = dataset_builder.info
        # TODO: this could use a mapper
        return {
            "description": info.description,
            "homepage": info.homepage,
            "download_size": info.download_size,
            "version": info.version,
        }


HFDatasetType.instance_classes = HFDataset
HFDatasetType.instance_class = HFDataset


@weave.op(input_type={}, output_type=weave.types.List(HFDatasetType()))
def datasets():
    return weave.List([HFDataset(name) for name in hf_datasets.list_datasets()])


class HFInternalBaseModelOutputType(weave.types.Type):
    instance_classes = transformers.modeling_outputs.BaseModelOutput

    def save_instance(self, obj, artifact, name):
        with artifact.new_file(f"{name}.pickle", binary=True) as f:
            pickle.dump(obj, f)

    def load_instance(self, artifact, name, extra=None):
        with artifact.open(f"{name}.pickle", binary=True) as f:
            return pickle.load(f)


class HFModelType(weave.types.ObjectType):
    def property_types(self):
        return {"name": weave.types.String()}


class BaseModelOutputType(weave.types.ObjectType):
    def property_types(self):
        return {
            "model": HFModelType(),
            "model_input": pytorch.TorchTensorType(),
            "model_output": HFInternalBaseModelOutputType(),
        }


class ModelOutputAttentionType(weave.types.ObjectType):
    def property_types(self):
        return {
            "model_output": BaseModelOutputType(),
            "attention": weave.types.List(pytorch.TorchTensorType()),
        }


@weave.weave_class(weave_type=HFModelType)
@dataclasses.dataclass
class HFModel:
    name: str

    def tokenizer(self):
        return transformers.AutoTokenizer.from_pretrained(self.name)

    @weave.op(output_type=BaseModelOutputType())
    def call(self, inputs: str):
        tokenizer = transformers.AutoTokenizer.from_pretrained(self.name)
        model = transformers.AutoModel.from_pretrained(
            self.name, output_attentions=True
        )
        model_input = tokenizer.encode(inputs, return_tensors="pt")
        model_output = model(model_input)
        return BaseModelOutput(self, model_input, model_output)


@weave.weave_class(weave_type=BaseModelOutputType)
@dataclasses.dataclass
class BaseModelOutput:
    model: HFModel
    model_input: torch.Tensor
    model_output: transformers.modeling_outputs.BaseModelOutput

    @weave.op(output_type=ModelOutputAttentionType())
    def attention(self):
        return ModelOutputAttention(self, self.model_output[-1])


@weave.weave_class(weave_type=ModelOutputAttentionType)
@dataclasses.dataclass
class ModelOutputAttention:
    model_output: BaseModelOutput
    attention: list[torch.Tensor]


@weave.op(render_info={"type": "function"})
def model(name: str) -> HFModel:
    return HFModel(name)
