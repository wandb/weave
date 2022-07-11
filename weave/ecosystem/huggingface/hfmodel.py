import typing
import dataclasses
import pickle
import torch
import weave

import transformers

from .. import pytorch


# This tells Weave how to serialize BaseModelOutput
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
        return {
            "id": weave.types.String(),
            "sha": weave.types.String(),
            "pipeline_tag": weave.types.String(),
            "tags": weave.types.List(weave.types.String()),
            "downloads": weave.types.Int(),
            "likes": weave.types.Int(),
            "library_name": weave.types.optional(weave.types.String()),
        }


@weave.weave_class(weave_type=HFModelType)
@dataclasses.dataclass
class HFModel:
    id: str
    sha: str
    pipeline_tag: str
    tags: list[str]  # TODO: we need a Tag type
    downloads: int
    likes: int
    library_name: typing.Optional[str]
    # TODO: version?

    def tokenizer(self):
        return transformers.AutoTokenizer.from_pretrained(self.id)

    @weave.op()
    def get_id(self) -> str:
        return self.id

    @weave.op()
    def get_pipeline_tag(self) -> str:
        return self.pipeline_tag


HFModelType.instance_classes = HFModel


class BaseModelOutputType(weave.types.ObjectType):
    def property_types(self):
        return {
            "model": HFModelType(),
            "model_input": weave.types.String(),
            "encoded_model_input": pytorch.TorchTensorType(),
            "model_output": HFInternalBaseModelOutputType(),
        }


class ModelOutputAttentionType(weave.types.ObjectType):
    def property_types(self):
        return {
            "model_output": BaseModelOutputType(),
            "attention": weave.types.List(pytorch.TorchTensorType()),
        }


# TODO
#  - do we need to declare a new Object here?
#  - or can we just attached to existing model info?


@weave.weave_class(weave_type=BaseModelOutputType)
@dataclasses.dataclass
class BaseModelOutput:
    model: HFModel
    model_input: str
    encoded_model_input: torch.Tensor
    model_output: transformers.modeling_outputs.BaseModelOutput


@weave.weave_class(weave_type=ModelOutputAttentionType)
@dataclasses.dataclass
class ModelOutputAttention:
    model_output: BaseModelOutput
    attention: list[torch.Tensor]


class EmptyModelOutputTypedDict(typing.TypedDict):
    pass


class FullPipelineOutputType(weave.types.ObjectType):
    def property_types(self):
        return {
            "model": HFModelType(),
            "model_input": weave.types.String(),
            "model_output": weave.types.List(weave.types.TypedDict({})),
        }


@weave.weave_class(weave_type=FullPipelineOutputType)
@dataclasses.dataclass
class FullPipelineOutput:
    model: HFModel
    model_input: str
    model_output: typing.Any

    @weave.op(output_type=ModelOutputAttentionType())
    def attention(self):
        pipeline = self.model.pipeline()
        tokenizer = pipeline.tokenizer
        # re-initialize model with output_attentions=True
        model = pipeline.model.__class__.from_pretrained(
            self.model.id, output_attentions=True
        )
        encoded_input = tokenizer.encode(self.model_input, return_tensors="pt")
        model_output = model(encoded_input)
        bmo = BaseModelOutput(self.model, self.model_input, encoded_input, model_output)
        return ModelOutputAttention(bmo, model_output[-1])
