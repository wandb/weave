import dataclasses
import pickle
import huggingface_hub
import transformers
import torch
import typing

import weave
from .. import pytorch

from . import hfmodel
from . import model_textclassification
from . import model_textgeneration


def full_model_info_to_hfmodel(
    info: huggingface_hub.hf_api.ModelInfo,
) -> hfmodel.HFModel:
    kwargs = {
        "_id": info.modelId,
        "_sha": info.sha,
        "_pipeline_tag": info.pipeline_tag,
        "_tags": info.tags,
        "_downloads": getattr(info, "downloads", 0),
        "_likes": getattr(info, "likes", 0),
        "_library_name": getattr(info, "library_name", None),
    }
    if info.pipeline_tag == "text-classification":
        return model_textclassification.HFModelTextClassification(**kwargs)
    elif info.pipeline_tag == "text-generation":
        return model_textgeneration.HFModelTextGeneration(**kwargs)
    return hfmodel.HFModel(**kwargs)


@weave.op(render_info={"type": "function"})
def models() -> list[hfmodel.HFModel]:
    api = huggingface_hub.HfApi()
    return [full_model_info_to_hfmodel(info) for info in api.list_models(full=True)]


@weave.op()
def models_render(
    models: weave.Node[list[hfmodel.HFModel]],
) -> weave.panels.Table:
    return weave.panels.Table(
        models,
        columns=[
            lambda model: model.id(),
            lambda model: model.sha(),
            lambda model: model.pipeline_tag(),
            lambda model: model.tags(),
            lambda model: model.downloads(),
            lambda model: model.likes(),
            lambda model: model.library_name(),
        ],
    )


@weave.op(render_info={"type": "function"})
def model_refine_output_type(id: str) -> weave.types.Type:
    api = huggingface_hub.HfApi()
    info = api.model_info(id)
    if info.pipeline_tag == "text-classification":
        return model_textclassification.HFModelTextClassificationType()
    if info.pipeline_tag == "text-generation":
        return model_textgeneration.HFModelTextGenerationType()
    raise Exception(
        "Huggingface model type '%s' not yet supported. Add support in ecosystem/huggingface."
        % info.pipeline_tag
    )


@weave.op(render_info={"type": "function"}, refine_output_type=model_refine_output_type)
def model(id: str) -> hfmodel.HFModel:
    api = huggingface_hub.HfApi()
    info = api.model_info(id)
    return full_model_info_to_hfmodel(info)


@weave.op()
def model_render(
    model_node: weave.Node[hfmodel.HFModel],
) -> weave.panels.Card:
    # All methods callable on X are callable on weave.Node[X], but
    # the types arent' setup properly, so cast to tell the type-checker
    # TODO: Fix!
    model = typing.cast(hfmodel.HFModel, model_node)
    return weave.panels.Card(
        title=model.id(),
        subtitle="HuggingFace Hub Model",
        content=[
            weave.panels.CardTab(
                name="Overview",
                content=weave.panels.Group(
                    items=[
                        weave.panels.LabeledItem(item=model.id(), label="ID"),
                        weave.panels.LabeledItem(
                            item=model.pipeline_tag(), label="Pipeline tag"
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
