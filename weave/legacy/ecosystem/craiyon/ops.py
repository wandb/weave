import base64
import io
import requests
from PIL import Image
import weave


class ServiceError(Exception):
    def __init__(self, status_code):
        self.status_code = status_code


@weave.op(render_info={"type": "function"})
def generate(prompt: str) -> list[Image.Image]:
    if prompt is None:
        return None
    r = requests.post("https://bf.dallemini.ai/generate", json={"prompt": prompt})
    if r.status_code == 200:
        json = r.json()
        images = json["images"]
        images = [Image.open(io.BytesIO(base64.b64decode(img))) for img in images]
        return images
    else:
        raise ServiceError(r.status_code)
