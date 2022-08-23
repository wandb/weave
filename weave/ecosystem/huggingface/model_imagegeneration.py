import logging

import diffusers
from PIL import Image
import weave

from . import hfmodel


@weave.type()
class FullImageGenerationPipelineOutput(hfmodel.FullPipelineOutput):

    _model: "HFModelImageGeneration"
    _model_input: str
    _model_output: list[Image.Image]

    @weave.op()
    def model_input(self) -> str:
        return self._model_input

    @weave.op()
    def model_output(self) -> list[Image.Image]:
        return self._model_output

    @weave.op()
    def model_name(self) -> str:
        return weave.use(self._model.id())


@weave.type()
class HFModelImageGeneration(hfmodel.HFModel):
    @weave.op()
    def pipeline(self) -> diffusers.DiffusionPipeline:
        """This is its own op so the pipeline can be cached."""
        result = diffusers.DiffusionPipeline.from_pretrained(
            self._pipeline_tag,
        )

        # side effect: move model to cuda
        try:
            result.to("cuda")
        except:
            logging.info("using CPU for pipeline")
        else:
            logging.info("using GPU for pipeline")

        return result

    @weave.op()
    def call(self, input: str) -> FullImageGenerationPipelineOutput:
        output = weave.use(self.pipeline())(input)
        return FullImageGenerationPipelineOutput(self, input, output)
