import typing
import dataclasses
import transformers

import weave

from . import hfmodel


# We have to forward-declare the Weave types to avoid circular reference
# issues that weave.type() can't resolve yet.


class HFModelTextGenerationType(hfmodel.HFModelType):
    pass


class FullTextGenerationPipelineOutputType(hfmodel.FullPipelineOutputType):
    def property_types(self):
        return {
            "_model": HFModelTextGenerationType(),
            "model_input": weave.types.String(),
            "model_output": weave.types.List(
                weave.types.TypedDict(
                    {
                        "generated_text": weave.types.String(),
                    }
                )
            ),
        }


class TextGenerationPipelineOutput(typing.TypedDict):
    generated_text: str


@weave.weave_class(weave_type=FullTextGenerationPipelineOutputType)
@dataclasses.dataclass
class FullTextGenerationPipelineOutput(hfmodel.FullPipelineOutput):
    _model: "HFModelTextGeneration"
    model_input: str
    model_output: list[TextGenerationPipelineOutput]


FullTextGenerationPipelineOutputType.instance_classes = FullTextGenerationPipelineOutput


@weave.type()
class FullTextGenerationPanel(weave.Panel):
    id = "FullTextGenerationPanel"
    input_node: weave.Node[FullTextGenerationPipelineOutput]

    @weave.op()
    def render(self) -> weave.panels.Group:
        output = typing.cast(FullTextGenerationPipelineOutput, self.input_node)
        return weave.panels.Group(
            preferHorizontal=True,
            items={
                "input": weave.panels.LabeledItem(
                    label="input", item=output.model_input
                ),
                "output": weave.panels.LabeledItem(
                    label="output", item=output.model_output
                ),
            },
        )


@weave.weave_class(weave_type=HFModelTextGenerationType)
@dataclasses.dataclass
class HFModelTextGeneration(hfmodel.HFModel):
    @weave.op()
    def pipeline(
        self,
    ) -> transformers.pipelines.Pipeline:
        return transformers.pipeline(
            self._pipeline_tag,
            model=self._id,
        )

    @weave.op()
    # TODO: There are many more arguments for text generation. Some of the arguments
    #    are pipeline arguments, others are passed to the underlying model's .generate()
    #    method. Need to find the docs for each of those.
    #    It'd be nice to call these different types, and therefore have different signatures
    #    for this call!
    def call(self, input: str) -> FullTextGenerationPipelineOutput:
        output = weave.use(self.pipeline())(input)
        return FullTextGenerationPipelineOutput(self, input, output)

    @weave.op()
    # TODO: There are many more arguments for text generation. Some of the arguments
    #    are pipeline arguments, others are passed to the underlying model's .generate()
    #    method. Need to find the docs for each of those.
    #    It'd be nice to call these different types, and therefore have different signatures
    #    for this call!
    def call_list(
        self, input: typing.List[str]
    ) -> typing.List[FullTextGenerationPipelineOutput]:
        output = map(self.pipeline(), input)
        return [
            FullTextGenerationPipelineOutput(self, i, o)
            for (i, o) in zip(input, output)
        ]


HFModelTextGenerationType.instance_classes = HFModelTextGeneration
