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
            "_model": HFModelTextClassificationType(),
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


class ClassificationResultType(weave.types.ObjectType):
    def property_types(self):
        return {
            "_model_name": weave.types.String(),
            "model_input": weave.types.String(),
            "_score": weave.types.Float(),
            "_label": weave.types.String(),
        }


@weave.weave_class(weave_type=ClassificationResultType)
@dataclasses.dataclass
class ClassificationResult:
    _model_name: str
    model_input: str
    _score: float
    _label: str

    @weave.op()
    def model_name(self) -> str:
        return self._model_name

    @weave.op()
    def score(self) -> float:
        return self._score

    @weave.op()
    def label(self) -> str:
        return self._label


ClassificationResultType.instance_classes = ClassificationResult


@weave.op()
def classification_result_render(
    results: weave.Node[list[ClassificationResult]],
) -> weave.panels.Table:
    from .huggingface_models import huggingface

    return weave.panels.Table(
        results,
        columns=[
            lambda result_row: weave.panels.WeaveLink(
                result_row.model_name(), to=lambda input: huggingface().model(input)  # type: ignore
            ),
            lambda result_row: result_row.model_input,
            lambda result_row: result_row.score(),
            lambda result_row: result_row.label(),
        ],
    )


class TextClassificationPipelineOutput(typing.TypedDict):
    label: str
    score: float


@weave.weave_class(weave_type=FullTextClassificationPipelineOutputType)
@dataclasses.dataclass
class FullTextClassificationPipelineOutput(hfmodel.FullPipelineOutput):
    _model: "HFModelTextClassification"
    model_input: str
    model_output: list[TextClassificationPipelineOutput]

    @weave.op()
    def model_name(self) -> str:
        return weave.use(self._model.id())


FullTextClassificationPipelineOutputType.instance_classes = (
    FullTextClassificationPipelineOutput
)


@weave.op()
def full_text_classification_output_render(
    output_node: weave.Node[FullTextClassificationPipelineOutput],
) -> weave.panels.Group2:
    output = typing.cast(FullTextClassificationPipelineOutput, output_node)
    return weave.panels.Group2(
        preferHorizontal=True,
        items={
            "input": weave.panels.LabeledItem(label="input", item=output.model_input),
            "output": weave.panels.LabeledItem(
                label="output",
                item=weave.panels.Plot(
                    input_node=typing.cast(weave.Node, output.model_output),
                    x=lambda class_score: class_score["score"],
                    y=lambda class_score: class_score["label"],
                ),
            ),
        },
    )


@weave.weave_class(weave_type=HFModelTextClassificationType)
@dataclasses.dataclass
class HFModelTextClassification(hfmodel.HFModel):
    @weave.op()
    def pipeline(
        self, return_all_scores: bool = True
    ) -> transformers.pipelines.text_classification.TextClassificationPipeline:
        return transformers.pipeline(
            self._pipeline_tag,
            model=self._id,
            return_all_scores=return_all_scores,
        )

    @weave.op()
    def call(self, input: str) -> FullTextClassificationPipelineOutput:
        output = weave.use(self.pipeline(True))(input)
        return FullTextClassificationPipelineOutput(self, input, output)

    def _call_list(
        self, input: typing.List[str]
    ) -> typing.List[FullTextClassificationPipelineOutput]:
        output = list(map(weave.use(self.pipeline()), input))
        return [
            FullTextClassificationPipelineOutput(self, i, o)
            for (i, o) in zip(input, output)
        ]

    @weave.op()
    def call_list(self, input: list[str]) -> list[FullTextClassificationPipelineOutput]:
        return self._call_list(input)


@weave.op()
def apply_models(
    models: list[HFModelTextClassification], inputs: list[str]
) -> list[ClassificationResult]:
    results = [model._call_list(inputs) for model in models]
    retval: list[ClassificationResult] = []
    for i, result in enumerate(results):
        for item in result:
            for output in item.model_output:
                retval.append(
                    ClassificationResult(
                        _model_name=models[i]._id,
                        model_input=item.model_input,
                        _score=output["score"],
                        _label=output["label"],
                    )
                )
    return retval


HFModelTextClassificationType.instance_classes = HFModelTextClassification
