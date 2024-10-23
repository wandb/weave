from typing import Type

from pydantic import BaseModel


class Collection(BaseModel):
    name: str
    base_model_spec: Type[BaseModel]


def class_all_bases_names(cls: type) -> list[str]:
    # Don't include cls and don't include object
    return [c.__name__ for c in cls.mro()[1:-1]]


def make_python_object_from_dict(collection: Collection, dict_val: dict) -> BaseModel:
    return {
        "_type": collection.name,
        **dict_val,
        "_class_name": collection.base_model_spec.__name__,
        "_bases": class_all_bases_names(collection.base_model_spec),
    }
