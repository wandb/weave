import typing
import dataclasses
import transformers

import weave

from . import hfmodel


# We have to forward-declare the Weave types to avoid circular reference
# issues that weave.type() can't resolve yet.


class HFModelTextClassificationType(hfmodel.HFModelType):
    _base_type = hfmodel.HFModelType()


class FullTextClassificationPipelineOutputType(weave.types.ObjectType):
    _base_type = hfmodel.FullPipelineOutputType()

    def property_types(self):
        return {
            "model": HFModelTextClassificationType(),
            "model_input": weave.types.String(),
            "model_output": weave.types.List(
                weave.types.TypedDict(
                    {
                        "score": weave.types.Float(),
                        "label": weave.types.String(),
                    }
                )
            ),
        }


class TextClassificationPipelineOutput(typing.TypedDict):
    label: str
    score: float


@weave.weave_class(weave_type=FullTextClassificationPipelineOutputType)
@dataclasses.dataclass
class FullTextClassificationPipelineOutput(hfmodel.FullPipelineOutput):
    model: "HFModelTextClassification"
    model_input: str
    model_output: TextClassificationPipelineOutput

    @weave.op()
    def get_model_input(self) -> str:
        return self.model_input

    @weave.op()
    def get_model_output(self) -> TextClassificationPipelineOutput:
        return self.model_output


FullTextClassificationPipelineOutputType.instance_classes = (
    FullTextClassificationPipelineOutput
)


@weave.op()
def full_text_classification_output_render(
    output_node: weave.Node[FullTextClassificationPipelineOutput],
) -> weave.panels.Group:
    output = typing.cast(FullTextClassificationPipelineOutput, output_node)
    return weave.panels.Group(
        prefer_horizontal=True,
        items=[
            weave.panels.LabeledItem(label="input", item=output.get_model_input()),
            weave.panels.LabeledItem(label="output", item=output.get_model_output()),
        ],
    )


@weave.weave_class(weave_type=HFModelTextClassificationType)
@dataclasses.dataclass
class HFModelTextClassification(hfmodel.HFModel):
    def pipeline(
        self, return_all_scores=False
    ) -> transformers.pipelines.text_classification.TextClassificationPipeline:
        return transformers.pipeline(
            self._pipeline_tag,
            model=self._id,
            return_all_scores=return_all_scores,
        )

    @weave.op()
    def call(self, input: str) -> FullTextClassificationPipelineOutput:
        output = self.pipeline()(input)
        return FullTextClassificationPipelineOutput(self, input, output)


HFModelTextClassificationType.instance_classes = HFModelTextClassification
