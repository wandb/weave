import replicate
import os
import tempfile
import weave

from PIL import Image

import requests
import shutil
import logging

logger = logging.getLogger(__name__)

from tenacity import (
    before_sleep_log,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)


try:
    with open(os.path.expanduser("~/.replicate_api_token")) as f:
        os.environ["REPLICATE_API_TOKEN"] = f.read().strip()
except FileNotFoundError:
    pass

retry_replicate_decorator = retry(
    reraise=True,
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=4, max=10),
    retry=(retry_if_exception_type(replicate.exceptions.ModelError)),
    before_sleep=before_sleep_log(logger, logging.WARNING),
)


def download_file(url, local_path):
    r = requests.get(url, stream=True)
    if r.status_code == 200:
        with open(local_path, "wb") as f:
            r.raw.decode_content = True
            shutil.copyfileobj(r.raw, f)


@weave.op()
@retry_replicate_decorator
def stable_diffusion(prompt: str) -> Image.Image:
    print("Running stable diffusion", prompt)
    model = replicate.models.get("stability-ai/stable-diffusion")
    image_url = model.predict(prompt=prompt)[0]
    image_file = tempfile.NamedTemporaryFile()
    download_file(image_url, image_file.name)
    image_file.seek(0)
    return Image.open(image_file)


def replicate_image_to_text(image: Image.Image, model_id: str) -> str:
    print("Running %s: %s" % (model_id, image))
    model = replicate.models.get(model_id)
    # save image to a temporary directory and upload it to Replicate
    with tempfile.TemporaryDirectory() as d:
        image.save(os.path.join(d, "image.png"))
        result = model.predict(image=open(os.path.join(d, "image.png"), "rb"))
    return result


@weave.op()
@retry_replicate_decorator
def img2prompt(image: Image.Image) -> str:
    return replicate_image_to_text(image, "methexis-inc/img2prompt")


@weave.op()
@retry_replicate_decorator
def clip_prefix_caption(image: Image.Image) -> str:
    return replicate_image_to_text(image, "rmokady/clip_prefix_caption")
