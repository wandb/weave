import io
import PIL
import PIL.Image
import base64
import binascii

from .. import api as weave
from .. import weave_types as types
from .. import errors


class ImageType(types.Type):
    name = "image"


# Things that all images have:
#   Type info (things we need to know at call time / type time)
#     width, height, channels
#
#     content ID (hash)
#     ability to get pixels, rows, columns etc
#     detailed type information, like which channel maps to what human concept
#
# Image files have
#     file size, hash, etc
#     format (png)


class PILImageType(types.Type):
    name = "pil-image"
    instance_class = PIL.Image.Image
    instance_classes = PIL.Image.Image

    # TODO: format is enum?
    # Hmm, even format is part of a saved image file, not part of a PIL Image
    # But dimensions and whatnot should be part of this definition
    def __init__(self, width: int = 5, height: int = 5, mode: str = "L"):
        self.width = width
        self.height = height
        self.mode = mode  # TODO: enum

    def _to_dict(self):
        return {"width": self.width, "height": self.height, "mode": self.mode}

    @classmethod
    def from_dict(cls, d):
        return cls(d["width"], d["height"], d["mode"])

    def assign_type(self, other: types.Type):
        if not isinstance(other, PILImageType):
            return types.Invalid()
        # TODO: we want to handle this by switch to number. However this logic
        #     should not need to be implemented by Type implementors. The underlying
        #     system can handle like ObjectType does.
        if self.width != other.width:
            raise errors.WeaveTypeError("image types have different widths")
        if self.height != other.height:
            raise errors.WeaveTypeError("image types have different heights")
        if self.mode != other.mode:
            raise errors.WeaveTypeError("image types have different modes")
        return self

    @classmethod
    def type_of_instance(cls, obj: PIL.Image.Image):
        return cls(obj.width, obj.height, obj.mode)

    @classmethod
    def save_instance(cls, obj: PIL.Image.Image, artifact, name):
        with artifact.new_file(f"{name}.png", binary=True) as f:
            obj.save(f)

    def load_instance(self, artifact, name, extra=None):
        with artifact.open(f"{name}.png", binary=True) as f:
            im = PIL.Image.open(f)
            im.load()
            return im


# I think I can fix PilImage To be a Weave Object instead of a custom type.
# The self._to_dict() method:
#   - by default saves any public, typed attributes on the class.
#   - you can override this and return a different dict.
#   - OR!
#   - you can return a Ref object, with extra attributes attached!
#   - That ref object itself will be converted to a dict.


@weave.weave_class(weave_type=PILImageType)
class PILImageOps:
    # TODO: should not need to hardcode type constants!
    @weave.op(input_type={"self": PILImageType(5, 5, "L")})
    def image_bytes(self) -> str:
        f = io.BytesIO()
        self.save(f, format="png")
        f.seek(0)
        return binascii.hexlify(f.read()).decode("ISO-8859-1")

    @weave.op()
    def width(self) -> int:
        return self.width
