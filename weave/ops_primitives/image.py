import dataclasses
import io
import PIL
import PIL.Image
import binascii

from .. import api as weave
from .. import weave_types as types


class ImageType(types.Type):
    name = "image"


@dataclasses.dataclass(frozen=True)
class PILImageType(types.Type):
    name = "pil_image"
    instance_classes = PIL.Image.Image

    width: types.Type = types.Int()
    height: types.Type = types.Int()
    mode: types.Type = types.String()

    @classmethod
    def type_of_instance(cls, obj: PIL.Image.Image):
        return cls(
            types.Const(types.Int(), obj.width),
            types.Const(types.Int(), obj.height),
            types.Const(types.String(), obj.mode),
        )

    @classmethod
    def save_instance(cls, obj: PIL.Image.Image, artifact, name):
        with artifact.new_file(f"{name}.png", binary=True) as f:
            obj.save(f)

    def load_instance(self, artifact, name, extra=None):
        with artifact.open(f"{name}.png", binary=True) as f:
            im = PIL.Image.open(f)
            im.load()
            return im


@weave.weave_class(weave_type=PILImageType)
class PILImageOps:
    # TODO: should not need to hardcode type constants!
    @weave.op(input_type={"self": PILImageType()})
    def image_bytes(self) -> str:
        f = io.BytesIO()
        self.save(f, format="png", compress_level=3)  # type: ignore
        f.seek(0)
        res = binascii.hexlify(f.read()).decode("ISO-8859-1")
        return res

    @weave.op()
    def width_(self) -> int:
        return self.width  # type: ignore
