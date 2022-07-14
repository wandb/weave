import typing
import dataclasses
import transformers

import weave

from . import hfmodel


# We have to forward-declare the Weave types to avoid circular reference
# issues that weave.type() can't resolve yet.


class HFModelTextGenerationType(hfmodel.HFModelType):
    _base_type = hfmodel.HFModelType()


class FullTextGenerationPipelineOutputType(weave.types.ObjectType):
    _base_type = hfmodel.FullPipelineOutputType()

    def property_types(self):
        return {
            "_model": HFModelTextGenerationType(),
            "_model_input": weave.types.String(),
            "_model_output": weave.types.List(
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
    _model_input: str
    _model_output: list[TextGenerationPipelineOutput]

    @weave.op()
    def model_input(self) -> str:
        return self._model_input

    @weave.op()
    def model_output(self) -> list[TextGenerationPipelineOutput]:
        return self._model_output


FullTextGenerationPipelineOutputType.instance_classes = FullTextGenerationPipelineOutput


@weave.op()
def full_text_generation_output_render(
    output_node: weave.Node[FullTextGenerationPipelineOutput],
) -> weave.panels.Group:
    output = typing.cast(FullTextGenerationPipelineOutput, output_node)
    return weave.panels.Group(
        prefer_horizontal=True,
        items=[
            weave.panels.LabeledItem(label="input", item=output.model_input()),
            weave.panels.LabeledItem(label="output", item=output.model_output()),
        ],
    )


@weave.weave_class(weave_type=HFModelTextGenerationType)
@dataclasses.dataclass
class HFModelTextGeneration(hfmodel.HFModel):
    @weave.op()
    def pipeline(
        self,
    ) -> transformers.pipelines.text_generation.TextGenerationPipeline:
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


HFModelTextGenerationType.instance_classes = HFModelTextGeneration
