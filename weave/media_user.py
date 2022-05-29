import dataclasses
import pyarrow as pa

from . import weave_types as types
from . import types_numpy


class Object:
    def __init__(self):
        pass


# These objects have a shared coordinate system,
# and a shared set of classes to choose from


# TODO: make these into a Typed Enum, available for both the Image
#     object itself, and in the ImageType
CHANNEL_MODE_GRAYSCALE = 0
CHANNEL_MODE_RGB = 1
CHANNEL_MODE_BGR = 2


class Image:
    # data is numpy array
    def __init__(self, channel_mode, data):
        self.channel_mode = channel_mode
        self.data = data


@dataclasses.dataclass
class ImageType(types.ObjectType):
    name = "image"
    # TODO: require at least 2 dimensions, no more than 3
    instance_classes = Image
    instance_class = Image

    channel_mode: types.Int
    data: types_numpy.NumpyArrayType

    def property_types(self):
        return {"channel_mode": self.channel_mode, "data": self.data}


class Box:
    def __init__(self, l, t, w, h):
        self.l = l
        self.t = t
        self.w = w
        self.h = h


class BoxType(types.ObjectType):
    name = "box"
    instance_classes = Box
    instance_class = Box

    def property_types(self):
        return {"l": types.Int(), "t": types.Int(), "w": types.Int(), "h": types.Int()}


class ImageWithMetadata(object):
    def __init__(self, image, boxes=[]):
        self.image = image
        self.boxes = boxes
        # self._masks = {}

    def add_box(self, box):
        self.boxes.append(box)

    # def add_mask(self, mask):
    #     self._masks.append(mask)


@dataclasses.dataclass
class ImageWithMetadataType(types.ObjectType):
    name = "imagewithmetadata"
    instance_classes = ImageWithMetadata
    instance_class = ImageWithMetadata

    image: ImageType

    def property_types(self):
        return {
            "image": self.image,
            # TODO: boxes is optional
            # TODO: boxes is actually a Dict
            "boxes": types.List(BoxType()),
        }


# Additional (older) code for media.py. Keeping because I want to
#    use something like the type structure here to test WB types.


# class Classes(object):
#     class Class(object):
#         def __init__(self, id, name):
#             self._id = id
#             self._name = name

#     def __init__(self):
#         self._classes = []

#     def add_class(self, class_):
#         self._classes.append(class_)

# class ClassBox(object):
#     def __init__(self, class_, box):
#         self._class = class_
#         self._box = box

# class InstanceBox(object):
#     def __init__(self, instance_, box):
#         self._instance = instance_
#         self._box = box

# class InstaceMask(object):
#     def __init__(self, data, instances):
#         self._instances = instances
#         self._data = data

# class SemanticMask(object):
#     def __init__(self, data, classes):
#         self._classes = classes
#         self._data = data

# class List:
#     def __init__(self):
#         self._items = []

#     def add(self, item):
#         self._items.append(item)

# # fully embedded arrow table
# MODE_NESTED_ARROW = 'nested_arrow'

# # separate pandas tables with fk refs for nesting
# MODE_NORMALIZED_PANDAS = 'normalized_pandas'

# # equivalent to wandb.Table
# #     tricky because pointers don't exactly happen at object
# #     boundaries? well it can, we just need to separate objects more
# MODE_FILE_POINTERS_JSON = 'file_pointers_json'

# # serialized objects always need to become:
# #    primitives: python string, int, float boolean
# #        numpy/tensorflow/whatever primitives, int16 etc
# #    arrays: python lists
# #        numpy arrays, tensors etc
# #    dicts
# #    pointers to other objects

# def save(obj, mode):
#     if mode == MODE_NESTED_ARROW:
#         obj.to_arrow()
#     else:
#         if not isinstance(obj, List):
#             raise Exception('not implemented')
#         if mode == MODE_NESTED_ARROW:
#             result = []
#             for item in obj:
#                 return result
#             # as we go we want to convert to arrow types...?

#             # 1. convert objs to nested dicts, leaving numpy arrays intact
#             # 2. infer arrow schema
#             # 3. construct arrow table and save
#             pass
#         elif mode == MODE_NORMALIZED_PANDAS:
#             # 1. convert objs to flat dicts, storing pointers to sub-objs, collecting
#             #    them in their own tables or numpy arrays
#             # 2. save everything at the end
#             pass
#         elif mode == MODE_FILE_POINTERS_JSON:
#             # 1. convert everything to nested dicts like NESTED_ARROW, but save image
#             #    data as image files and use pointers for them
#             # 2. save
#             pass
#     # so for all of these, we care about the relationships between objects
#     #   and we might have different policies for numpy data
#     # all objects need to convert to dicts or primitives
#     # but we need to expression relationships (one to one, or one to many
#     #     [or many to many?])
#     #     lists are one to many relationships when encountered inside an
#     #         object


# # Issue: heterogeneity.
# #   if we build up a list of numpy arrays, and they are not the same shapes,
# #   we can't save them as a single numpy array. They must be kept separate.

# # TODO:
# #   Should also test how to save coco dataset and other formats using
# #       this model. And how they'd be converted to Table.

# # Its more like what we want is a Collection object, where you can add items and
# #    get results back
# # But how do you do coll.column()
