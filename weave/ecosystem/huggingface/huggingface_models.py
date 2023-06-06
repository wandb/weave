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


@weave.type()
class HuggingfaceModelsPanel(weave.Panel):
    id = "HuggingfaceModelsPanel"
    input_node: weave.Node[list[hfmodel.HFModel]]

    @weave.op()
    def render(self) -> weave.panels.Table:
        return weave.panels.Table(
            self.input_node,
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


@weave.type()
class HuggingfaceModelPanel(weave.Panel):
    id = "HuggingfaceModelPanel"
    input_node: weave.Node[hfmodel.HFModel]

    @weave.op(pure=False)
    def render(self) -> weave.panels.Card:
        model = typing.cast(hfmodel.HFModel, self.input_node)
        return weave.panels.Card(
            title=model.id(),
            subtitle="HuggingFace Hub Model",
            content=[
                weave.panels.CardTab(
                    name="Model Card",
                    content=weave.panels.PanelMarkdown(model.readme()),  # type: ignore
                ),
                weave.panels.CardTab(
                    name="Metadata",
                    content=weave.panels.Group(
                        items={
                            "id": weave.panels.LabeledItem(item=model.id(), label="ID"),
                            "pipeline_tag": weave.panels.LabeledItem(
                                item=model.pipeline_tag(), label="Pipeline tag"
                            ),
                        }
                    ),
                ),
                # Broke in panel refactor. Don't have concrete op name available here so
                # can't get the right type for the output.
                # weave.panels.CardTab(
                #     name="Inference Logs",
                #     content=weave.panels.Table(
                #         weave.ops.used_by(model, model.call.op_name()),
                #         columns=[
                #             lambda run: run.output.model_input,
                #             lambda run: run.output.model_output[0]["generated_text"],
                #         ],
                #     ),
                # ),
            ],
        )


@weave.type()
class HuggingFacePackage:
    @weave.op(hidden=True)
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

    @weave.op()
    def models(self) -> list[hfmodel.HFModel]:
        api = huggingface_hub.HfApi()
        return [full_model_info_to_hfmodel(info) for info in api.list_models(full=True)]


@weave.op(render_info={"type": "function"})
def huggingface() -> HuggingFacePackage:
    return HuggingFacePackage()


@weave.type()
class HuggingfacePackagePanel(weave.Panel):
    id = "HuggingfacePackagePanel"
    input_node: weave.Node[HuggingFacePackage]

    @weave.op()
    def render(self) -> weave.panels.Card:
        pack = typing.cast(HuggingFacePackage, self.input_node)  # type: ignore
        return weave.panels.Card(
            title="Huggingface Package",
            subtitle="Browse Models and Datasets",
            content=[
                weave.panels.CardTab(name="Models", content=pack.models()),  # type: ignore
            ],
        )
