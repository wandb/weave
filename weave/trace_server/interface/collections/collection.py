from typing import Type

from pydantic import BaseModel


class Collection(BaseModel):
    name: str
    base_model_spec: Type[BaseModel]


def make_python_object_from_dict(
    type_name: str, class_name: str, bases: list[str], dict_val: dict
) -> BaseModel:
    return {
        "_type": type_name,
        **dict_val,
        # "_class_name": class_name,
        # "_bases": bases,
    }
