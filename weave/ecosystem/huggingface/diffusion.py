import logging

import diffusers
from PIL import Image
import weave

from . import hfmodel


@weave.type()
class HFModelDiffusion(hfmodel.HFModel):
    @weave.op()
    def pipeline(self) -> diffusers.DiffusionPipeline:
        """This is its own op so the pipeline can be cached."""
        return diffusers.DiffusionPipeline.from_pretrained(
            self._id,
        )

    @weave.op()
    def call(self, input: str) -> list[Image.Image]:

        pipeline = weave.use(self.pipeline())

        # side effect: move model to cuda if its not already there
        try:
            pipeline.to("cuda")
        except RuntimeError:
            logging.info("using CPU for pipeline")
        else:
            logging.info("using GPU for pipeline")

        return pipeline(input)["sample"]
