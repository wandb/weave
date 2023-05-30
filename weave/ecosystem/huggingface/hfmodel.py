import typing
import huggingface_hub
import dataclasses
import pickle
import torch
import weave
from ... import op_def_type


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


class HFInternalPipelineType(weave.types.Type):
    instance_classes = transformers.pipelines.base.Pipeline

    def save_instance(self, obj, artifact, name):
        with artifact.new_file(f"{name}.pickle", binary=True) as f:
            pickle.dump(obj, f)

    def load_instance(self, artifact, name, extra=None):
        with artifact.open(f"{name}.pickle", binary=True) as f:
            return pickle.load(f)


class HFModelType(weave.types.ObjectType):
    def property_types(self):
        return {
            "_id": weave.types.String(),
            "_sha": weave.types.String(),
            "_pipeline_tag": weave.types.optional(weave.types.String()),
            "_tags": weave.types.List(weave.types.String()),
            "_downloads": weave.types.Int(),
            "_likes": weave.types.Int(),
            "_library_name": weave.types.optional(weave.types.String()),
            "call": op_def_type.OpDefType(),
        }


@weave.weave_class(weave_type=HFModelType)
@dataclasses.dataclass
class HFModel:
    _id: str
    _sha: str
    _pipeline_tag: str
    _tags: list[str]  # TODO: we need a Tag type
    _downloads: int
    _likes: int
    _library_name: typing.Optional[str]
    # TODO: version?

    # This is the type of of the call op that will be overridden by child-classes.
    # Just putting it here to get nice autocomplete, but there's probably a better
    # and more general way to do this.
    # TODO: Fix
    # call: weave.OpDef

    def tokenizer(self):
        return transformers.AutoTokenizer.from_pretrained(self._id)

    @weave.op()
    def readme(self) -> weave.ops.Markdown:
        readme = huggingface_hub.hf_hub_download(self._id, "README.md")
        # quick hack: remove the metadata header from the readme
        readme_contents = ""
        break_count = 0
        for l in open(readme).readlines():
            if l.startswith("---"):
                break_count += 1
            elif break_count > 1:
                readme_contents += l
        # if we failed to parse out the header
        if len(readme_contents) < 1:
            readme_contents = open(readme).read()
        return weave.ops.Markdown(readme_contents)

    @weave.op()
    def id(self) -> str:
        return self._id

    @weave.op()
    def sha(self) -> str:
        return self._sha

    @weave.op()
    def pipeline_tag(self) -> str:
        return self._pipeline_tag

    @weave.op()
    def tags(self) -> list[str]:
        return self._tags

    @weave.op()
    def downloads(self) -> int:
        return self._downloads

    @weave.op()
    def likes(self) -> int:
        return self._likes

    @weave.op()
    def library_name(self) -> typing.Optional[str]:
        return self._library_name


HFModelType.instance_classes = HFModel


class BaseModelOutputType(weave.types.ObjectType):
    def property_types(self):
        return {
            "_model": HFModelType(),
            "model_input": weave.types.String(),
            "_encoded_model_input": pytorch.TorchTensorType(),
            "model_output": HFInternalBaseModelOutputType(),
        }


class ModelOutputAttentionType(weave.types.ObjectType):
    def property_types(self):
        return {
            "model_output": BaseModelOutputType(),
            "_attention": weave.types.List(pytorch.TorchTensorType()),
        }


@weave.weave_class(weave_type=BaseModelOutputType)
@dataclasses.dataclass
class BaseModelOutput:
    _model: HFModel
    model_input: str
    _encoded_model_input: torch.Tensor
    model_output: transformers.modeling_outputs.BaseModelOutput


@weave.weave_class(weave_type=ModelOutputAttentionType)
@dataclasses.dataclass
class ModelOutputAttention:
    model_output: BaseModelOutput
    _attention: list[torch.Tensor]


class FullPipelineOutputType(weave.types.ObjectType):
    def property_types(self):
        return {
            "_model": HFModelType(),
            "model_input": weave.types.String(),
            "model_output": weave.types.List(weave.types.TypedDict({})),
        }


@weave.weave_class(weave_type=FullPipelineOutputType)
@dataclasses.dataclass
class FullPipelineOutput:
    _model: HFModel
    model_input: str
    model_output: typing.Any

    @weave.op(output_type=ModelOutputAttentionType())
    def attention(self):
        pipeline = weave.use(self._model.pipeline())
        tokenizer = pipeline.tokenizer
        # re-initialize model with output_attentions=True
        model = pipeline.model.__class__.from_pretrained(
            self._model._id, output_attentions=True
        )
        encoded_input = tokenizer.encode(self.model_input, return_tensors="pt")
        model_output = model(encoded_input)
        bmo = BaseModelOutput(
            self._model, self.model_input, encoded_input, model_output
        )
        return ModelOutputAttention(bmo, model_output[-1])
