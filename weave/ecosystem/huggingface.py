import dataclasses
import pickle
import huggingface_hub
import datasets as hf_datasets
import transformers
import torch
import typing

import weave
from . import pytorch


class HFDatasetInfoTypedDict(typing.TypedDict):
    id: str
    lastModified: str
    tags: list[str]
    description: str
    # citation: str
    # sha: str
    # downloads: int


@weave.op(render_info={"type": "function"})
def datasets() -> list[HFDatasetInfoTypedDict]:
    api = huggingface_hub.HfApi()
    return [
        {
            "id": dataset_info.id,
            "lastModified": dataset_info.lastModified,
            "tags": dataset_info.tags or [],
            "description": dataset_info.description,
            # "downloads": dataset_info.downloads,
        }
        for dataset_info in api.list_datasets()
    ]


# TODO: we really need finer grained numeric types!
def hf_feature_type_to_type(type_):
    if isinstance(type_, dict):
        prop_types = {}
        for key, type_ in type_.items():
            prop_types[key] = hf_feature_type_to_type(type_)
        return weave.types.TypedDict(prop_types)
    elif isinstance(type_, hf_datasets.features.features.Sequence):
        return weave.types.List(hf_feature_type_to_type(type_.feature))
    elif isinstance(type_, hf_datasets.features.features.Image):
        return weave.ops.PILImageType()
    elif isinstance(type_, hf_datasets.features.features.ClassLabel):
        # TODO: this should be a classes type!!!!!
        return weave.types.Int()
    else:
        dtype = type_.dtype
        if dtype == "int32":
            return weave.types.Int()
        elif dtype == "int64":
            return weave.types.Int()
        elif dtype == "float32":
            return weave.types.Float()
        elif dtype == "string":
            return weave.types.String()
    raise weave.errors.WeaveTypeError("unhandled hf type: %s" % type_)


@weave.op(render_info={"type": "function"})
def dataset_refine_output_type(name: str) -> weave.types.Type:
    ds = hf_datasets.load_dataset(name, split="train", streaming=True)
    prop_types = {}
    for key, type_ in ds.features.items():
        prop_types[key] = hf_feature_type_to_type(type_)
    return weave.types.List(weave.types.TypedDict(prop_types))


@weave.op(
    render_info={"type": "function"},
    output_type=weave.types.List(weave.types.TypedDict({})),
)
def dataset(name: str):
    ds = hf_datasets.load_dataset(name, split="train", streaming=True)

    rows = []
    for _, row in zip(range(100), iter(ds)):
        rows.append(row)
    return rows


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


@weave.weave_class(weave_type=HFModelType)
@dataclasses.dataclass
class HFModel:
    id: str
    sha: str
    pipeline_tag: str

    # TODO: we need a Tag type
    tags: list[str]

    # Skip siblings for now, for models it seems to be a list of files associated
    # with the model
    # siblings: list[typing.Any]

    # Skip author, its just the org prefix before the slash in id?
    # author: str
    downloads: int
    likes: int
    library_name: typing.Optional[str]

    # TODO: version
    # No...

    def tokenizer(self):
        return transformers.AutoTokenizer.from_pretrained(self.id)

    def pipeline(self, return_all_scores=False):
        return transformers.pipeline(
            self.pipeline_tag,
            model=self.id,
            return_all_scores=return_all_scores,
        )

    @weave.op()
    def get_id(self) -> str:
        return self.id

    @weave.op()
    def get_pipeline_tag(self) -> str:
        return self.pipeline_tag

    @weave.op(output_type=BaseModelOutputType())
    def call(self, input: str):
        # TODO: these take awhile to load. We should create them on init, and
        #     ensure auto-caching of MemRefs works.
        tokenizer = transformers.AutoTokenizer.from_pretrained(self.id)
        model = transformers.AutoModel.from_pretrained(self.id)
        # model = transformers.AutoModel.from_pretrained(self.id, output_attentions=True)

        encoded_input = tokenizer.encode(input, return_tensors="pt")
        model_output = model(encoded_input)
        return BaseModelOutput(self, input, encoded_input, model_output)


HFModelType.instance_classes = HFModel


@weave.weave_class(weave_type=BaseModelOutputType)
@dataclasses.dataclass
class BaseModelOutput:
    model: HFModel
    model_input: str
    encoded_model_input: torch.Tensor
    model_output: transformers.modeling_outputs.BaseModelOutput

    @weave.op(output_type=ModelOutputAttentionType())
    def attention(self):
        return ModelOutputAttention(self, self.model_output[-1])


@weave.weave_class(weave_type=ModelOutputAttentionType)
@dataclasses.dataclass
class ModelOutputAttention:
    model_output: BaseModelOutput
    attention: list[torch.Tensor]


class HFModelInfoTypedDict(typing.TypedDict):
    id: str
    pipeline_tag: str
    tags: list[str]

    # citation: str
    # sha: str
    # downloads: int


def full_model_info_to_hfmodel(info: huggingface_hub.hf_api.ModelInfo) -> HFModel:
    return HFModel(
        id=info.modelId,
        sha=info.sha,
        pipeline_tag=info.pipeline_tag,
        tags=info.tags,
        downloads=getattr(info, "downloads", 0),
        likes=getattr(info, "likes", 0),
        library_name=getattr(info, "library_name", None),
    )


@weave.op(render_info={"type": "function"})
def models() -> list[HFModel]:
    api = huggingface_hub.HfApi()
    return [full_model_info_to_hfmodel(info) for info in api.list_models(full=True)]


@weave.op()
def models_render(
    models: weave.Node[list[HFModel]],
) -> weave.panels.Table:
    return weave.panels.Table(
        models,
        columns=[
            lambda model: model.get_id(),
            lambda model: model.get_pipeline_tag(),
        ],
    )


@weave.op(render_info={"type": "function"})
def model(id: str) -> HFModel:
    api = huggingface_hub.HfApi()
    info = api.model_info(id)
    return full_model_info_to_hfmodel(info)


@weave.op()
def model_render(
    model_node: weave.Node[HFModel],
) -> weave.panels.Card:
    # All methods callable on X are callable on weave.Node[X], but
    # the types arent' setup properly, so cast to tell the type-checker
    # TODO: Fix!
    model = typing.cast(HFModel, model_node)
    return weave.panels.Card(
        title=model.get_id(),
        subtitle="HuggingFace Hub Model",
        content=[
            weave.panels.CardTab(
                name="Overview",
                content=weave.panels.Group(
                    items=[
                        weave.panels.LabeledItem(item=model.get_id(), label="ID"),
                        weave.panels.LabeledItem(
                            item=model.get_pipeline_tag(), label="Pipeline tag"
                        ),
                    ]
                ),
            ),
        ],
    )


### Trying out a "module" pattern here. Not quite right...


# @weave.type()
# class HuggingFaceModule:
#     @weave.op()
#     def model(self, name: str) -> HFModel:
#         return HFModel(name)


# @weave.op(render_info={"type": "function"})
# def huggingface() -> HuggingFaceModule:
#     return HuggingFaceModule()
