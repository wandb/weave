import typing
import dataclasses
import transformers

import weave

from . import hfmodel


class HFModelTextClassificationType(hfmodel.HFModelType):
    pass


class FullTextClassificationPipelineOutputType(hfmodel.FullPipelineOutputType):
    def property_types(self):
        return {
            "model": hfmodel.HFModelType(),
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


@weave.weave_class(weave_type=HFModelTextClassificationType)
@dataclasses.dataclass
class HFModelTextClassification(hfmodel.HFModel):
    def pipeline(
        self, return_all_scores=False
    ) -> transformers.pipelines.text_classification.TextClassificationPipeline:
        return transformers.pipeline(
            self.pipeline_tag,
            model=self.id,
            return_all_scores=return_all_scores,
        )

    @weave.op()
    def call(self, input: str) -> FullTextClassificationPipelineOutput:
        output = self.pipeline()(input)
        return FullTextClassificationPipelineOutput(self, input, output)


HFModelTextClassificationType.instance_classes = HFModelTextClassification
