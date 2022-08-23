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
        result = diffusers.DiffusionPipeline.from_pretrained(
            self._id,
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
    def call(self, input: str) -> list[Image.Image]:
        return weave.use(self.pipeline())(input)["sample"]
