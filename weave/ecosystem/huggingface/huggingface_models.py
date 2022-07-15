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


@weave.op()
def models_render(
    models: weave.Node[list[hfmodel.HFModel]],
) -> weave.panels.Table:
    return weave.panels.Table(
        models,
        columns=[
            lambda model_row: weave.panels.WeaveLink(
                model_row.id(), to=lambda input: huggingface().model(input)  # type: ignore
            ),
            lambda model_row: model_row.sha(),
            lambda model_row: model_row.pipeline_tag(),
            lambda model_row: model_row.tags(),
            lambda model_row: model_row.downloads(),
            lambda model_row: model_row.likes(),
            lambda model_row: model_row.library_name(),
        ],
    )


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


@weave.type()
class HuggingFacePackage:
    @weave.op(render_info={"type": "function"})
    def model_refine_output_type(self, id: str) -> weave.types.Type:
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

    @weave.op(refine_output_type=model_refine_output_type)
    def model(self, id: str) -> hfmodel.HFModel:
        api = huggingface_hub.HfApi()
        info = api.model_info(id)
        return full_model_info_to_hfmodel(info)

    @weave.op(render_info={"type": "function"})
    def models(self) -> list[hfmodel.HFModel]:
        api = huggingface_hub.HfApi()
        return [full_model_info_to_hfmodel(info) for info in api.list_models(full=True)]


@weave.op(render_info={"type": "function"})
def huggingface() -> HuggingFacePackage:
    return HuggingFacePackage()


@weave.op()
def hfm_render(
    hfm_node: weave.Node[HuggingFacePackage],
) -> weave.panels.Card:
    hfm_node = typing.cast(HuggingFacePackage, hfm_node)  # type: ignore
    return weave.panels.Card(
        title="Huggingface Package",
        subtitle="Browse Models and Datasets",
        content=[
            weave.panels.CardTab(name="Models", content=hfm_node.models()),  # type: ignore
        ],
    )
